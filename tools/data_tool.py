import json
from agents import function_tool
from faker import Faker

fake = Faker("zh_CN")


@function_tool
def generate_test_data(data_type: str, count: int = 1) -> str:
    """生成测试数据。

    Args:
        data_type: 数据类型 (employee/dish/order/address/phone/name/email)
        count: 生成数量
    """
    results = []

    for _ in range(count):
        if data_type == "employee":
            results.append({
                "username": fake.user_name(),
                "name": fake.name(),
                "phone": fake.phone_number(),
                "password": "123456",
                "idNumber": fake.ssn(),
            })
        elif data_type == "dish":
            results.append({
                "name": fake.word() + "菜",
                "price": fake.random_int(min=1000, max=9999),
                "categoryId": fake.random_int(min=1, max=20),
            })
        elif data_type == "address":
            results.append({
                "consignee": fake.name(),
                "phone": fake.phone_number(),
                "detail": fake.address(),
            })
        elif data_type == "phone":
            results.append(fake.phone_number())
        elif data_type == "name":
            results.append(fake.name())
        elif data_type == "email":
            results.append(fake.email())
        else:
            results.append({"value": fake.word()})

    return json.dumps(results if count > 1 else results[0], ensure_ascii=False, indent=2)
