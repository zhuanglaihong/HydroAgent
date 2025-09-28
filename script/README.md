# Script Directory

本目录包含HydroAgent系统的可执行文件，用于运行特定的任务

## 测试文件概览

### run_knowledge_update.py
  - 主要用于知识库更新，支持全量重建、增量更新、备份恢复
  - 支持命令行参数：--rebuild、--update、--stats、--backup、--restore
  - 提供静默模式和日志记录功能