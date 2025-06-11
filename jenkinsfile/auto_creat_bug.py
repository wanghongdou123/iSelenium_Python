import os
import json
import requests
from collections import defaultdict
from typing import Dict, List

# 禅道配置
ZENTAO_URL = "http://www.zentaopms.com:8081/zentao/qa.html"  # 替换为你的禅道地址
ZENTAO_USER = "Auto456"  # 禅道用户名
ZENTAO_PASSWORD = "Auto456"  # 禅道密码
PRODUCT_ID = 4  # 产品ID
MODULE_ID = 159  # 模块ID


class ZentaoBugReporter:
    def __init__(self):
        self.session = None
        self.existing_bugs_cache = set()  # 缓存已存在的Bug标题，用于去重

    def login_zentao(self):
        """登录禅道获取session"""
        self.session = requests.Session()
        login_url = f"{ZENTAO_URL}/user-login.html"
        data = {
            "account": ZENTAO_USER,
            "password": ZENTAO_PASSWORD,
            "keepLogin": "on"
        }
        try:
            response = self.session.post(login_url, data=data)
            response.raise_for_status()
            print("禅道登录成功")
        except Exception as e:
            print(f"禅道登录失败: {str(e)}")
            raise

    def parse_allure_results(self, allure_results_dir: str) -> Dict[str, List[dict]]:
        """
        解析Allure生成的JSON结果文件，返回失败用例
        :param allure_results_dir: Allure结果目录路径
        :return: 字典格式的失败用例 {测试名称: [失败详情1, 失败详情2]}
        """
        failures = defaultdict(list)

        if not os.path.exists(allure_results_dir):
            raise FileNotFoundError(f"Allure结果目录不存在: {allure_results_dir}")

        # 遍历allure结果目录中的所有JSON文件
        for file_name in os.listdir(allure_results_dir):
            if file_name.endswith('-result.json'):
                file_path = os.path.join(allure_results_dir, file_name)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        test_data = json.load(f)

                        if test_data.get('status') in ('failed', 'broken'):
                            case_name = test_data.get('name', 'Unnamed Test')
                            full_name = test_data.get('fullName', case_name)

                            # 提取失败信息
                            failure = test_data.get('failure') or {}
                            message = failure.get('message', 'No failure message')
                            stack_trace = failure.get('stackTrace', 'No stack trace')

                            # 提取步骤信息
                            steps = []
                            for step in test_data.get('steps', []):
                                step_status = step.get('status', 'N/A')
                                step_name = step.get('name', 'Unnamed step')
                                steps.append(f"{step_name}: {step_status}")

                            # 提取测试参数（如果有参数化测试）
                            parameters = []
                            for param in test_data.get('parameters', []):
                                parameters.append(f"{param.get('name')}: {param.get('value')}")

                            failures[case_name].append({
                                'full_name': full_name,
                                'message': message,
                                'stack_trace': stack_trace,
                                'steps': steps,
                                'parameters': parameters,
                                'file_path': file_path
                            })
                except Exception as e:
                    print(f"解析文件 {file_name} 失败: {str(e)}")
                    continue

        return failures

    def check_duplicate_bug(self, case_name: str) -> bool:
        """
        检查禅道中是否已存在相同Bug
        :param case_name: 测试用例名称
        :return: 是否存在重复Bug
        """
        if not self.session:
            raise RuntimeError("请先登录禅道")

        # 先从缓存中查找
        bug_title = f"[UI自动化失败] {case_name}"
        if bug_title in self.existing_bugs_cache:
            return True

        # 查询禅道
        search_url = f"{ZENTAO_URL}/bug-search-{PRODUCT_ID}.html"
        params = {
            "productID": PRODUCT_ID,
            "searchTitle": bug_title,
            "status": "active"
        }

        try:
            response = self.session.get(search_url, params=params)
            response.raise_for_status()

            # 简单检查标题是否已存在
            if bug_title in response.text:
                self.existing_bugs_cache.add(bug_title)
                return True
            return False
        except Exception as e:
            print(f"查询重复Bug失败: {str(e)}")
            return False  # 查询失败时默认不认为是重复，继续创建

    def create_zentao_bug(self, case_name: str, failure_details: dict):
        """
        在禅道中创建Bug
        :param case_name: 测试用例名称
        :param failure_details: 失败详情
        """
        if not self.session:
            raise RuntimeError("请先登录禅道")

        bug_url = f"{ZENTAO_URL}/bug-create-{PRODUCT_ID}-{MODULE_ID}.html"

        # 构建Bug内容
        title = f"[UI自动化失败] {case_name}"
        steps = "\n".join(failure_details["steps"])
        parameters = "\n".join(failure_details["parameters"]) if failure_details["parameters"] else "无"

        content = f"""
**失败用例**: {failure_details["full_name"]}
**测试参数**: 
{parameters}

**错误信息**: 
{failure_details["message"]}

**堆栈跟踪**: 
{failure_details["stack_trace"]}

**测试步骤**:
{steps}

**相关文件**: {failure_details["file_path"]}
"""

        data = {
            "product": PRODUCT_ID,
            "module": MODULE_ID,
            "title": title,
            "steps": content,
            "openedBuild[]": "trunk",
            "severity": 3,  # 严重程度
            "type": "codeerror",
            "pri": 3,  # 优先级
        }

        try:
            response = self.session.post(bug_url, data=data)
            response.raise_for_status()

            if "bug-view" in response.url:
                print(f"成功创建Bug: {title}")
                self.existing_bugs_cache.add(title)  # 添加到缓存
            else:
                print(f"创建Bug可能失败，请检查禅道: {title}")
        except Exception as e:
            print(f"创建Bug失败: {str(e)}")

    def report_failures_to_zentao(self, allure_results_dir: str):
        """
        主方法：解析Allure结果并提交失败用例到禅道
        :param allure_results_dir: Allure结果目录路径
        """
        try:
            # 1. 登录禅道
            self.login_zentao()

            # 2. 解析Allure结果
            print("正在解析Allure测试结果...")
            failures = self.parse_allure_results(allure_results_dir)

            if not failures:
                print("没有发现失败的测试用例")
                return

            print(f"发现 {len(failures)} 个失败的测试用例")

            # 3. 处理失败用例
            for case_name, failure_list in failures.items():
                if not self.check_duplicate_bug(case_name):
                    for failure in failure_list:
                        self.create_zentao_bug(case_name, failure)
                else:
                    print(f"已存在相同Bug，跳过创建: {case_name}")

        except Exception as e:
            print(f"处理失败: {str(e)}")
        finally:
            print("处理完成")


if __name__ == "__main__":
    # 使用示例
    reporter = ZentaoBugReporter()
    reporter.report_failures_to_zentao(
        "/Users/wanghongdou/.jenkins/workspace/iSelenium_test/iSelenium_Python/allure-results")
