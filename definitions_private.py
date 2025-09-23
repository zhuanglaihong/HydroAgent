import os
# 项目根目录
PROJECT_DIR = os.getcwd()
# 结果保存路径
RESULT_DIR = "result"
# 数据路径
DATASET_DIR = "data/camels_11532500"
# 水文模型参数路径
PARAM_RANGE_FILE = "hydromodel/models/param.yaml"
# 大模型API密钥
OPENAI_API_KEY = "sk-50be7aaa64564360bb2a6dbd2e2db325"
# 大模型平台链接
OPENAI_BASE_URL="对应平台的BASE_URL"

'''对于window系统
打开powershell,永久设置环境变量
# 用您的百炼API Key代替YOUR_DASHSCOPE_API_KEY
[Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "YOUR_DASHSCOPE_API_KEY", [EnvironmentVariableTarget]::User)

临时设置（仅当前会话有效）
$env:DASHSCOPE_API_KEY = "YOUR_DASHSCOPE_API_KEY"

查看是否设置成功
echo $env:DASHSCOPE_API_KEY

对于CMD
永久设置环境变量
setx DASHSCOPE_API_KEY "YOUR_DASHSCOPE_API_KEY"
临时设置（仅当前会话有效）
set DASHSCOPE_API_KEY=YOUR_DASHSCOPE_API_KEY
查看设置是否成功
echo %DASHSCOPE_API_KEY%
'''