import random
import string
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from pynocaptcha import CloudFlareCracker
from loguru import logger
from web3 import Web3
import time
from dotenv import load_dotenv
import os

load_dotenv()

NO_CAP_TOKEN = os.getenv("NO_CAP_TOKEN")
IPV6_PROXY = os.getenv("IPV6_PROXY")
IPV4_PROXY = os.getenv("IPV4_PROXY")
THREADS = os.getenv("THREADS")
TOTAL = os.getenv("TOTAL")

# 配置日志
logger.add("faucet.log", rotation="30 MB", level="INFO")


class FaucetClaimer:
    def __init__(self, num_threads=5, max_retries=3):
        """
        初始化水龙头领取器
        :param num_threads: 并发线程数
        :param max_retries: 最大重试次数
        """
        self.num_threads = num_threads
        self.max_retries = max_retries
        self.w3 = Web3()

    @staticmethod
    def generate_random_string(length=10):
        """
        生成指定长度的随机字母数字字符串
        :param length: 字符串长度
        :return: 随机字符串
        """
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def get_random_proxy(self, is_ipv6=False):
        """
        获取随机代理地址
        :param is_ipv6: 是否使用IPv6代理
        :return: 代理地址字符串
        """
        random_str = self.generate_random_string()
        if is_ipv6:
            return "http://" + IPV6_PROXY.replace(IPV6_PROXY[IPV6_PROXY.find("-s_") + 3:IPV6_PROXY.find(":")],
                                                  random_str)
        return "http://" + IPV4_PROXY.replace(IPV4_PROXY[IPV4_PROXY.find("-s_") + 3:IPV4_PROXY.find(":")], random_str)

    def get_captcha(self):
        """
        获取验证码token
        :return: 验证码token或None
        """
        while True:
            try:
                cracker = CloudFlareCracker(
                    user_token=str(NO_CAP_TOKEN),
                    sitekey="0x4AAAAAAA2QYSDpMpFM53JQ",
                    href="https://faucet.vana.com/mainnet",
                    proxy=self.get_random_proxy(True),
                    developer_id="hLf08E",
                    debug=False,
                    show_ad=False
                )
                if captcha := cracker.crack().get('token'):
                    logger.info("Successfully cracked captcha")
                    return captcha
                logger.warning("Failed to get captcha, retrying...")
            except Exception as e:
                logger.error(f"Error getting captcha: {str(e)}")

    def claim(self, address, captcha):
        """
        尝试领取水龙头
        :param address: 以太坊地址
        :param captcha: 验证码token
        :return: 是否成功
        """
        headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'content-type': 'text/plain;charset=UTF-8',
            'origin': 'https://faucet.vana.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://faucet.vana.com/mainnet',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

        data = f'{{"address":"{address}","captcha":"{captcha}","network":"mainnet"}}'

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url='https://faucet.vana.com/api/transactions',
                    headers=headers,
                    data=data,
                    proxies={"https": self.get_random_proxy()}
                )

                logger.info(f"Claim attempt {attempt + 1}: {response.text}")

                if response.status_code == 200:
                    logger.success(f"Claim successful for address {address}")
                    return True

            except Exception as e:
                logger.error(f"Claim attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)

        return False

    def process_account(self):
        """
        处理单个账户的完整流程
        :return: 是否成功
        """
        account = self.w3.eth.account.create()
        logger.info(f"Generated address: {account.address}")

        try:
            if captcha := self.get_captcha():
                if self.claim(account.address, captcha):
                    with open('success.txt', 'a') as f:
                        f.write(f'{account.address}----{account.key.hex()}\n')
                        f.flush()
                    logger.success(f"Saved successful claim to file: {account.address}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error processing account: {str(e)}")
            return False

    def run(self, num_accounts=10):
        """
        运行主程序
        :param num_accounts: 要处理的账户数量
        :return: 成功数量
        """
        logger.info(f"Starting faucet claim process with {self.num_threads} threads")
        successful_claims = 0

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [executor.submit(self.process_account) for _ in range(num_accounts)]

            for future in as_completed(futures):
                if future.result():
                    successful_claims += 1

        logger.info(f"Completed claiming process. Successful claims: {successful_claims}/{num_accounts}")
        return successful_claims


if __name__ == '__main__':
    logger.warning("感谢选择 nocaptcha, 我们只做别人做不到的(手动狗头)~")
    logger.warning("欢迎推荐注册, 官网地址: https://www.nocaptcha.io/register?c=hLf08E")
    logger.warning("代码配套代理ip(无需在外网环境就可以使用): https://app.nstproxy.com/register?i=r0wYrb")
    claimer = FaucetClaimer(num_threads=int(THREADS))
    claimer.run(num_accounts=int(TOTAL))
