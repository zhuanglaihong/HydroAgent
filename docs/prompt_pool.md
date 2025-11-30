  ---
  HydroAgent的Prompt Pool工作机制

  📋 核心架构

  HydroAgent的Prompt Pool系统由两个核心组件组成：

  1. PromptPool (hydroagent/core/prompt_pool.py) - 核心提示词池
  2. PromptManager (hydroagent/utils/prompt_manager.py) - 动态提示词管理器（辅助工具）

  🎯 主要用途和使用位置

  Prompt Pool主要在 TaskPlanner 智能体中使用，工作流程如下：

  IntentAgent → TaskPlanner (使用PromptPool) → InterpreterAgent → RunnerAgent → DeveloperAgent
                      ↑
                创建并使用PromptPool

  🔧 核心功能

  1. 历史案例存储 (prompt_pool.py:92-129)

  pool.add_history(
      task_type="calibration",
      intent={"model_name": "gr4j", "basin_id": "01013500", ...},
      config={...},  # 完整配置
      result={...},  # 执行结果（NSE等指标）
      success=True
  )

  - 自动保存到 prompt_pool/history.json
  - 最多保存50条记录（可配置）
  - 包含任务类型、配置、结果、时间戳

  2. 相似案例检索 (prompt_pool.py:130-196)

  简单规则匹配算法（不是复杂的向量检索）：

  | 匹配项    | 得分   |
  |--------|------|
  | 模型名称相同 | +1.0 |
  | 算法相同   | +0.8 |
  | 任务类型相同 | +0.7 |
  | 流域ID相同 | +0.5 |

  similar = pool.get_similar_cases(
      intent={"model_name": "gr4j", "algorithm": "SCE_UA", ...},
      limit=3,
      only_success=True  # 只返回成功案例
  )

  3. 上下文提示词生成 (prompt_pool.py:198-244)

  核心功能：将基础提示词增强为带历史案例的完整提示词

  complete_prompt = pool.generate_context_prompt(
      base_prompt="请根据以下配置执行模型率定...",
      intent=current_intent,
      error_log=previous_error  # 可选
  )

  生成的提示词结构：
  [基础提示词]

  ### 📚 历史成功案例参考

  **案例1**:
  - 模型: gr4j
  - 算法: SCE_UA
  - 算法参数: {"rep": 500, "ngs": 200}
  - 性能: NSE=0.75

  **案例2**:
  - 模型: gr4j
  - 算法: DE
  - 算法参数: {"max_generations": 100}
  - 性能: NSE=0.68

  ### ⚠️ 上次执行失败 (如果有错误日志)
  [错误信息]
  **请根据错误信息调整配置，避免重复错误。**

  🔄 完整工作流程

  1. 初始化阶段 (orchestrator.py:199-212)

  # Orchestrator初始化时创建PromptPool
  prompt_pool = PromptPool(pool_dir=workspace / "prompt_pool")
  task_planner = TaskPlanner(
      llm_interface=llm,
      prompt_pool=prompt_pool,  # 注入到TaskPlanner
      workspace_dir=workspace
  )

  2. 任务规划阶段 (task_planner.py:179-186)

  # TaskPlanner为每个子任务存储提示词
  for subtask in subtasks:
      prompt = self._generate_subtask_prompt(subtask, intent_result)
      self.prompt_pool.store_prompt(
          task_id=subtask.task_id,
          prompt=prompt,
          params=subtask.parameters
      )

  3. 生成提示词时 (task_planner.py:540-569)

  def _generate_subtask_prompt(self, subtask, intent_result, error_log=None):
      # 1. 获取基础提示词模板
      base_prompt = self._get_base_prompt(subtask.task_type)

      # 2. 注入任务参数
      base_prompt = self._inject_parameters(base_prompt, subtask.parameters)

      # 3. 使用PromptPool增强（添加历史案例）
      complete_prompt = self.prompt_pool.generate_context_prompt(
          base_prompt=base_prompt,
          intent=intent_result,
          error_log=error_log
      )

      return complete_prompt

  4. 任务完成后 (orchestrator.py:395-407)

  # 所有子任务执行完毕后，保存到历史记录
  for subtask_result in execution_results:
      task_planner.prompt_pool.add_history(
          task_type=subtask_result["task_type"],
          intent=intent_data,
          config=config,
          result=subtask_result,
          success=subtask_result.get("success", False)
      )

  📊 实际使用场景

  场景1：标准率定（无历史案例）

  用户查询: "率定GR4J模型，流域01013500"
           ↓
  TaskPlanner生成的提示词 = 基础模板（只有任务描述）

  场景2：相似任务（有历史案例）

  用户查询: "率定GR4J模型，流域01022500"
           ↓
  PromptPool检索到相似案例（gr4j + SCE_UA）
           ↓
  TaskPlanner生成的提示词 = 基础模板 + 2个成功案例（NSE=0.75, NSE=0.68）
           ↓
  LLM参考历史案例的算法参数配置（如 rep=500）

  场景3：错误重试（有错误日志）

  第一次率定失败 → error_log = "参数范围过大导致收敛失败"
           ↓
  PromptPool生成提示词 = 基础模板 + 历史案例 + 错误警告
           ↓
  LLM调整配置避免同样错误

  🎯 Prompt Pool vs Prompt Manager

  | 特性    | PromptPool          | PromptManager           |
  |-------|---------------------|-------------------------|
  | 位置    | core/prompt_pool.py | utils/prompt_manager.py |
  | 用途    | 历史案例管理              | 静态模板管理                  |
  | 使用者   | TaskPlanner         | 旧版代码（逐渐弃用）              |
  | 核心功能  | 案例检索、上下文增强          | 静态+Schema+动态拼接          |
  | 是否持久化 | ✅ 保存到JSON           | ❌ 内存中                   |

  PromptManager是早期设计，现在主要用于代码生成模板（build_code_generation_prompt函数），核心的任务规划已经切换到
  PromptPool。

  📁 数据存储

  workspace/
  └── prompt_pool/
      └── history.json          # 历史记录（最多50条）
          {
            "task_type": "calibration",
            "intent": {...},
            "config": {...},
            "result": {"NSE": 0.75},
            "success": true,
            "timestamp": "2025-11-30T..."
          }

  🚀 关键优势

  1. 自动学习：每次成功率定后自动保存经验
  2. 零向量计算：简单规则匹配，无需嵌入模型
  3. 错误避免：记录失败案例，提醒LLM避免同样错误
  4. 轻量级：只保存50条，避免token浪费

  ⚙️ 配置参数

  PromptPool(
      pool_dir=Path("prompt_pool"),  # 存储目录
      max_history=50                  # 最大历史记录数
  )

  ---
  总结：Prompt Pool是HydroAgent的"经验记忆系统"，主要在TaskPlanner中使用，通过简单的规则匹配来检索历史成功案例，帮助
  LLM更好地生成配置，避免重复错误。