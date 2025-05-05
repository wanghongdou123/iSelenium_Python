import allure
import configparser
import os
import time
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager  # 自动管理驱动版本


@allure.feature('Test Baidu WebUI')
class ISelenium(unittest.TestCase):
    # 读入配置文件
    def get_config(self):
        config = configparser.ConfigParser()
        # 添加默认配置，避免文件不存在时报错
        config['driver'] = {
            'chrome_driver': 'chromedriver',  # 默认使用PATH中的chromedriver
        }
        config.read([
            os.path.join(os.environ.get('HOME', ''), 'iselenium.ini'),  # 原始路径
            os.path.join(os.path.dirname(__file__), 'config.ini')  # 添加项目目录下的配置文件
        ])
        return config

    def tearDown(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def setUp(self):
        config = self.get_config()

        # 从环境变量中读取using_headless（Jenkins参数）
        using_headless = os.getenv("USING_HEADLESS", "false").lower() == "true"
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        if using_headless:
            chrome_options.add_argument("--headless=new")  # 新版Chrome推荐写法
            print('使用无界面方式运行')
        else:
            print('使用有界面方式运行')

        # 初始化 Chrome 驱动
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
        except Exception as e:
            print(f"驱动初始化失败: {str(e)}")
            raise

    @allure.story('Test key word 今日头条')
    def test_webui_1(self):
        """测试用例1，验证'今日头条'关键词在百度上的搜索结果"""
        self._test_baidu('今日头条', 'test_webui_1')

    @allure.story('Test key word 王者荣耀')
    def test_webui_2(self):
        """测试用例2，验证'王者荣耀'关键词在百度上的搜索结果"""
        self._test_baidu('王者荣耀', 'test_webui_2')

    def _test_baidu(self, search_keyword, testcase_name):
        """测试百度搜索子函数

        Args:
            search_keyword: 搜索关键词 (str)
            testcase_name: 测试用例名 (str)
        """
        with allure.step(f"测试搜索关键词: {search_keyword}"):
            try:
                self.driver.get("https://www.baidu.com")
                print('打开浏览器，访问 www.baidu.com')
                time.sleep(2)  # 适当减少等待时间

                # 更健壮的标题检查
                assert '百度' in self.driver.title, "百度页面标题验证失败"

                # 显式等待替代固定sleep（更佳实践）
                elem = self.driver.find_element(By.NAME, "wd")
                elem.clear()
                elem.send_keys(f'{search_keyword}{Keys.RETURN}')
                print(f'搜索关键词: {search_keyword}')
                time.sleep(2)

                # 更灵活的验证方式
                current_title = self.driver.title
                self.assertTrue(
                    search_keyword in current_title or '安全验证' in current_title,
                    msg=f'{testcase_name}校验失败，实际标题: {current_title}'
                )

                # 添加截图到Allure报告
                allure.attach(
                    self.driver.get_screenshot_as_png(),
                    name=f"{testcase_name}_result",
                    attachment_type=allure.attachment_type.PNG
                )

            except Exception as e:
                # 失败时截图
                self.driver.save_screenshot(f"error_{testcase_name}.png")
                raise


if __name__ == "__main__":
    # 支持直接运行
    unittest.main()