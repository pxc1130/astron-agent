# PR: 修复 Link 插件在工作流单步执行中 x-display 关闭字段仍返回的问题

## 1. 背景与问题

在“托管工具 + 工作流单步执行”场景下，用户将 `object/array` 子参数设置为关闭（`x-display: false`）后，返回结果中仍可能包含这些字段值。


## 2. 根因分析

核心根因是**两条执行链路不一致**：

1. `core/agent` 链路（`LinkPluginRunner`）已有/补齐了 `x-display` 响应过滤。  
2. `core/workflow` 链路（`Tool.run` in `link_client.py`）此前直接返回解析后的响应，**未按 response schema 执行过滤**。

因此在工作流单步执行中会出现“关闭字段仍可见”。

---

## 3. 代码改动清单

### A. 功能修复主路径

1. [core/workflow/engine/nodes/plugin_tool/link_client.py](core/workflow/engine/nodes/plugin_tool/link_client.py)
- 新增 response schema 提取：`get_response_json_schema`
- 新增隐藏路径收集：`collect_hidden_json_paths`
- 新增单次遍历裁剪逻辑：`build_hidden_path_tree` / `prune_payload_by_path_tree` / `pop_hidden_fields`
- 新增过滤入口：`filter_response_by_schema`
- 在 `Tool.run` 成功分支中接入过滤（返回前执行）


2. [core/workflow/tests/engine/nodes/test_link_client_filter.py](core/workflow/tests/engine/nodes/test_link_client_filter.py)
- 新增工作流链路回归测试：
  - 隐藏 `email` + `address.street`
  - `address` 全子字段隐藏后，容器保留 `{}`


---

### B. 跨链路一致性

3. [core/agent/service/plugin/link.py](core/agent/service/plugin/link.py)
- 统一并完善响应过滤实现（与 workflow 链路一致的 trie 裁剪思路）
- 增加 `validate_response`：校验失败不阻断过滤，仅记录 warning
- 常量样式统一为类内大写：`HIDDEN_LEAF` / `REMOVED`

虽然本次主 bug 在 workflow 链路，但 agent/workflow 逻辑一致可避免行为分叉和后续二次缺陷。

4. [core/agent/tests/test_plugin_base_link_mcp_workflow.py](core/agent/tests/test_plugin_base_link_mcp_workflow.py)
- 增补 agent 侧过滤行为测试（对象、数组、深层嵌套、校验失败兜底）

---

### C. 验证与发布相关改动（非修复逻辑本体）

5. [core/agent/pyproject.toml](core/agent/pyproject.toml)
- 添加 `jsonschema` 依赖（用于 response schema 校验，确保过滤逻辑健壮性）

---

## 4. 处理逻辑说明（算法与行为）

1. 从 OpenAPI `responses` 中提取 response schema。  
2. 遍历 schema，收集所有 `x-display: false` 的 JSON 路径（支持对象嵌套与数组 `*`）。  
3. 将隐藏路径构建成 trie。  
4. 对响应 payload 做一次递归裁剪：
   - 命中隐藏叶子：
     - `dict` -> `{}`
     - `list` -> `[]`
     - 基础类型 -> 删除
   - 未命中：递归处理子节点
5. 返回过滤后的结构，保证“容器结构保留、敏感值剔除”。

这满足产品语义：
- 字段关闭后不展示值；
- 若整个对象/数组子字段都关闭，仍保留空容器，避免上层消费方结构断裂。

---

## 5. 验证结果

### 自动化测试
- agent 侧：`tests/test_plugin_base_link_mcp_workflow.py` 相关过滤用例通过
- workflow 侧：`tests/engine/nodes/test_link_client_filter.py` 新增用例通过


### 部署验证
- 本地手动测试：构造包含 `x-display: false` 字段的工具响应，验证工作流单步执行结果符合预期（敏感字段被过滤，容器结构保留）。

- 本地构建镜像：`docker build -t core-agent:local -f docker/astronAgent/Dockerfile .`
- compose 配置校验通过：`docker compose config`
- 容器启动成功：`core-agent`、`core-workflow` 均为本地镜像并处于 `Up`
- 手动验证原有用户场景： 输出符合预期
---

## 6. 风险与回滚

### 风险
- 若外部依赖（Kafka/网络）不可用，可能出现告警日志，但不影响本次过滤逻辑。
- response schema 缺失时，过滤会跳过（保持兼容）。

### 回滚
- 回滚以下文件到前一版本即可：
  - [core/workflow/engine/nodes/plugin_tool/link_client.py](core/workflow/engine/nodes/plugin_tool/link_client.py)
  - [core/agent/service/plugin/link.py](core/agent/service/plugin/link.py)
  - [docker/astronAgent/docker-compose.yaml](docker/astronAgent/docker-compose.yaml)

---

## 7. 评审建议

建议重点关注：
1. `Tool.run` 中过滤接入点是否位于“解析响应后、返回前”；
2. “全子字段关闭后保留空容器”的行为是否符合产品预期；
3. compose 本地构建策略是否与当前发布流程一致。
