"""
Auto-generated locustfile from YAML config
Dynamic token acquisition enabled: True
"""

from locust import HttpUser, task, between


class TestUser(HttpUser):
    wait_time = between(0.5, 2)
    host = "http://124.222.42.246:8080"
    token = None

    def on_start(self):
        """登录获取 token"""
        try:
            response = self.client.post(
                "/admin/employee/login",
                json={"username": "admin", "password": "123456"},
                headers={"Content-Type": "application/json"},
                name="登录获取Token",
            )
            if response.status_code == 200:
                data = response.json()
                # 解析 token_field 路径 (如 "data.token")
                self.token = data
                for key in "data.token".split("."):
                    if isinstance(self.token, dict):
                        self.token = self.token.get(key)
                    else:
                        self.token = None
                        break
                if not self.token:
                    self.token = None
            else:
                self.token = None
        except Exception as e:
            self.token = None

    @task(3)
    def task_0(self):
        """员工登录"""
        # 员工登录
        headers = {}
        with self.client.post(
            "/admin/employee/login",
            json={"username": "admin", "password": "123456"},
            headers=headers,
            name="员工登录",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def task_1(self):
        """分类查询"""
        # 查询分类列表
        headers = {}
        if self.token:
            headers["token"] = self.token
        with self.client.get(
            "/admin/category/list",
            headers=headers,
            name="查询分类列表",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status code: {response.status_code}")

    @task(5)
    def task_2(self):
        """菜品查询"""
        # 菜品分页查询
        headers = {}
        if self.token:
            headers["token"] = self.token
        with self.client.get(
            "/admin/dish/page",
            params={"page": 1, "pageSize": 10},
            headers=headers,
            name="菜品分页查询",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status code: {response.status_code}")

    @task(3)
    def task_3(self):
        """订单查询"""
        # 订单搜索
        headers = {}
        if self.token:
            headers["token"] = self.token
        with self.client.get(
            "/admin/order/conditionSearch",
            params={"page": 1, "pageSize": 10},
            headers=headers,
            name="订单搜索",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status code: {response.status_code}")

    @task(4)
    def task_4(self):
        """套餐查询"""
        # 套餐分页查询
        headers = {}
        if self.token:
            headers["token"] = self.token
        with self.client.get(
            "/admin/setmeal/page",
            params={"page": 1, "pageSize": 10},
            headers=headers,
            name="套餐分页查询",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status code: {response.status_code}")

    @task(2)
    def task_5(self):
        """店铺状态"""
        # 获取店铺状态
        headers = {}
        if self.token:
            headers["token"] = self.token
        with self.client.get(
            "/admin/shop/status",
            headers=headers,
            name="获取店铺状态",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status code: {response.status_code}")

