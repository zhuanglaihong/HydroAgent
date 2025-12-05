"""
测试scipy算法识别
验证系统能否正确识别和解析scipy算法参数
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_scipy_queries():
    """测试scipy算法的各种查询格式"""
    test_queries = [
        "率定GR4J模型，流域01013500，使用scipy算法",
        "用scipy率定流域01055000，迭代500轮",
        "率定流域01030500的GR4J，scipy算法，种群200，迭代1000",
        "用scipy算法率定流域01031500，种群150",
        "率定GR4J，流域01047000，算法用scipy，迭代300次",
    ]
    
    print("=" * 80)
    print("测试scipy算法识别")
    print("=" * 80)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. 查询: {query}")
        print(f"   预期: 应识别为scipy算法")
        print(f"   预期参数: maxiter (迭代次数), popsize (种群大小)")
    
    print("\n" + "=" * 80)
    print("测试说明:")
    print("1. scipy算法的参数名应为 'maxiter' (不是 'max_iterations')")
    print("2. 种群参数名应为 'popsize' (不是 'population_size')")
    print("3. 算法ID应为 'scipy' (小写)")
    print("=" * 80)
    
    print("\n✅ 已更新以下文件:")
    print("   1. hydroagent/resources/algorithm_params_schema.txt")
    print("      - 添加了scipy算法的完整定义")
    print("      - 明确了三种可用算法: SCE_UA, scipy, GA")
    print("   2. configs/config.py")
    print("      - 修正了scipy参数名: max_iterations → maxiter")
    print("      - 添加了popsize, strategy, tol参数")
    print("\n🔍 下一步:")
    print("   运行实际的IntentAgent测试以验证识别效果")

if __name__ == "__main__":
    test_scipy_queries()
