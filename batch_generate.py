#!/usr/bin/env python3
"""批量生成测试用例脚本 - 按模块逐个生成"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

from agent.main import generate_and_review

MODULES = [
    {
        "name": "菜品管理",
        "file": "testcases/dish/test_dish.yaml",
        "apis": """- POST /admin/dish 新增菜品
- PUT /admin/dish 修改菜品
- DELETE /admin/dish 批量删除菜品
- GET /admin/dish/list 菜品列表
- GET /admin/dish/page 菜品分页查询
- GET /admin/dish/{id} 根据ID查询菜品
- POST /admin/dish/status/{status} 菜品起售停售""",
    },
    {
        "name": "订单管理",
        "file": "testcases/order/test_order.yaml",
        "apis": """- GET /admin/order/conditionSearch 订单搜索
- GET /admin/order/details/{id} 订单详情
- GET /admin/order/statistics 订单统计
- PUT /admin/order/confirm 接单
- PUT /admin/order/rejection 拒单
- PUT /admin/order/cancel 取消订单
- PUT /admin/order/delivery/{id} 派送订单
- PUT /admin/order/complete/{id} 完成订单""",
    },
    {
        "name": "套餐管理",
        "file": "testcases/setmeal/test_setmeal.yaml",
        "apis": """- POST /admin/setmeal 新增套餐
- PUT /admin/setmeal 修改套餐
- DELETE /admin/setmeal 删除套餐
- GET /admin/setmeal/page 套餐分页查询
- GET /admin/setmeal/{id} 根据ID查询套餐
- POST /admin/setmeal/status/{status} 套餐起售停售""",
    },
    {
        "name": "店铺管理",
        "file": "testcases/shop/test_shop.yaml",
        "apis": """- GET /admin/shop/status 获取店铺营业状态
- PUT /admin/shop/{status} 设置店铺营业状态""",
    },
    {
        "name": "工作台",
        "file": "testcases/workspace/test_workspace.yaml",
        "apis": """- GET /admin/workspace/businessData 营业数据
- GET /admin/workspace/overviewOrders 订单概览
- GET /admin/workspace/overviewDishes 菜品概览
- GET /admin/workspace/overviewSetmeals 套餐概览""",
    },
    {
        "name": "数据报表",
        "file": "testcases/report/test_report.yaml",
        "apis": """- GET /admin/report/turnoverStatistics 营业额统计
- GET /admin/report/ordersStatistics 订单统计
- GET /admin/report/userStatistics 用户统计
- GET /admin/report/top10 销量排名Top10""",
    },
    {
        "name": "用户端地址",
        "file": "testcases/addressbook/test_addressbook.yaml",
        "apis": """- POST /user/addressBook 新增地址
- PUT /user/addressBook 修改地址
- DELETE /user/addressBook 删除地址
- GET /user/addressBook/list 地址列表
- GET /user/addressBook/{id} 根据ID查询
- GET /user/addressBook/default 获取默认地址
- PUT /user/addressBook/default 设置默认地址""",
    },
    {
        "name": "用户端购物车",
        "file": "testcases/shoppingcart/test_shoppingcart.yaml",
        "apis": """- POST /user/shoppingCart/add 添加购物车
- POST /user/shoppingCart/sub 减少购物车
- GET /user/shoppingCart/list 购物车列表
- DELETE /user/shoppingCart/clean 清空购物车""",
    },
    {
        "name": "用户端订单",
        "file": "testcases/user/test_user_order.yaml",
        "apis": """- POST /user/order/submit 提交订单
- GET /user/order/historyOrders 历史订单
- GET /user/order/orderDetail/{id} 订单详情
- PUT /user/order/cancel/{id} 取消订单
- PUT /user/order/payment 订单支付
- GET /user/order/reminder/{id} 催单
- POST /user/order/repetition/{id} 再来一单""",
    },
    {
        "name": "用户端菜品套餐",
        "file": "testcases/user/test_user_browse.yaml",
        "apis": """- GET /user/category/list 分类列表
- GET /user/dish/list 菜品列表
- GET /user/setmeal/list 套餐列表
- GET /user/setmeal/dish/{id} 套餐菜品
- GET /user/shop/status 店铺状态
- POST /user/user/login 微信登录
- POST /user/user/logout 退出登录""",
    },
]


def generate_module(module: dict):
    """为单个模块生成测试用例"""
    print(f"\n{'='*60}")
    print(f"正在生成: {module['name']}")
    print(f"{'='*60}")

    task = f"""请为{module['name']}模块生成完整测试用例，覆盖以下接口：

{module['apis']}

要求：
1. 每个接口至少 3 个用例（正常+异常+边界）
2. 直接输出 YAML，不要有其他文字
3. 用中文命名用例"""

    result = generate_and_review(task, max_rounds=2)

    os.makedirs(os.path.dirname(module["file"]), exist_ok=True)
    with open(module["file"], "w", encoding="utf-8") as f:
        clean = result.replace("```yaml", "").replace("```", "").strip()
        f.write(clean)

    print(f"✅ 已保存到 {module['file']}")


def main():
    print(f"开始批量生成测试用例，共 {len(MODULES)} 个模块")

    for i, module in enumerate(MODULES, 1):
        print(f"\n[{i}/{len(MODULES)}] {module['name']}")
        try:
            generate_module(module)
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            continue

    print(f"\n{'='*60}")
    print("全部完成！运行 python coverage.py 查看覆盖率")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
