# -*- coding: utf-8 -*-
# TencentBlueKing is pleased to support the open source community by making
# 蓝鲸智云 - 用户管理 (bk-user) available.
# Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
#     http://opensource.org/licenses/MIT
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions and
# limitations under the License.
#
# We undertake not to change the open source license (MIT license) applicable
# to the current version of the project delivered to anyone in the future.
import logging
import re
from typing import Callable, Optional

from bkuser.common.desensitize import desensitize_email, desensitize_phone
from bkuser.common.local import local

# 匹配 password 字段，支持如下格式：
# password=xxx
# password : xxx
# "password": "xxx"
# 'password' : 'xxx'
# 支持单双引号、冒号/等号、可选空格、内容可带引号或不带引号
PASSWORD_PATTERN = re.compile(r'(["\']?password["\']?\s*[:=]\s*)(["\']?)[^"\',;\s]+(\2)', re.IGNORECASE)

SECRET_PATTERN = re.compile(r'(["\']?secret["\']?\s*[:=]\s*)(["\']?)[^"\',;\s]+(\2)', re.IGNORECASE)

TOKEN_PATTERN = re.compile(r'(["\']?token["\']?\s*[:=]\s*)(["\']?)[^"\',;\s]+(\2)', re.IGNORECASE)

BK_SECRET_PATTERN = re.compile(r'(["\']?bk_secret["\']?\s*[:=]\s*)(["\']?)[^"\',;\s]+(\2)', re.IGNORECASE)

BK_APP_SECRET_PATTERN = re.compile(r'(["\']?bk_app_secret["\']?\s*[:=]\s*)(["\']?)[^"\',;\s]+(\2)', re.IGNORECASE)

BK_TOKEN_PATTERN = re.compile(r'(["\']?bk_token["\']?\s*[:=]\s*)(["\']?)[^"\',;\s]+(\2)', re.IGNORECASE)


class RequestIDFilter(logging.Filter):
    """
    request id log filter
    日志记录中增加 request id
    """

    def filter(self, record):
        record.request_id = local.request_id
        return True


class SensitiveInfoFilter(logging.Filter):
    """
    敏感信息脱敏 filter 基类。
    支持两种用法：
    1. 指定 pattern（正则表达式），自动用 repl 方法替换敏感内容。
    2. 指定 desensitize_func（自定义脱敏函数），对日志内容整体处理。
    子类只需指定 pattern 或 desensitize_func 即可。
    """

    desensitize_func: Optional[Callable[[str], str]] = None  # 自定义脱敏函数
    pattern: Optional[re.Pattern] = None  # 敏感信息正则表达式

    def repl(self, match: re.Match) -> str:
        """
        正则替换回调，所有敏感内容统一替换为 7 个 *。
        7 位 * 是为了避免与用户输入的 6/8 位 * 混淆。
        """
        return "*******"

    def filter(self, record: logging.LogRecord) -> bool:
        """
        日志过滤主逻辑：
        - 如果有自定义脱敏函数，优先用函数处理日志内容。
        - 否则如果有正则 pattern，则用 pattern 匹配并替换敏感内容。
        - 处理后将 record.args 置为 None，确保日志输出安全。
        """
        if self.desensitize_func:
            record.msg = self.desensitize_func(record.getMessage())
            record.args = None
        elif self.pattern:
            record.msg = self.pattern.sub(self.repl, record.getMessage())
            record.args = None
        return True


class PasswordFilter(SensitiveInfoFilter):
    """
    针对 password 字段的敏感信息脱敏过滤器。
    匹配所有常见 password 相关日志内容，并用 ******* 替换密码明文。
    """

    pattern = PASSWORD_PATTERN


class SecretFilter(SensitiveInfoFilter):
    """
    针对 secret 字段的敏感信息脱敏过滤器。
    匹配所有常见 secret 相关日志内容，并用 ******* 替换 secret 明文。
    """

    pattern = SECRET_PATTERN


class BkSecretFilter(SensitiveInfoFilter):
    """
    针对 bk_secret 字段的敏感信息脱敏过滤器。
    匹配所有常见 bk_secret 相关日志内容，并用 ******* 替换 bk_secret 明文。
    """

    pattern = BK_SECRET_PATTERN


class BkAppSecretFilter(SensitiveInfoFilter):
    """
    针对 bk_app_secret 字段的敏感信息脱敏过滤器。
    匹配所有常见 bk_app_secret 相关日志内容，并用 ******* 替换 bk_app_secret 明文。
    """

    pattern = BK_APP_SECRET_PATTERN


class BkTokenFilter(SensitiveInfoFilter):
    """
    针对 bk_token 字段的敏感信息脱敏过滤器。
    匹配所有常见 bk_token 相关日志内容，并用 ******* 替换 bk_token 明文。
    """

    pattern = BK_TOKEN_PATTERN


class TokenFilter(SensitiveInfoFilter):
    """
    针对 token 字段的敏感信息脱敏过滤器。
    匹配所有常见 token 相关日志内容，并用 ******* 替换 token 明文。
    """

    pattern = TOKEN_PATTERN


class PhoneNumberFilter(SensitiveInfoFilter):
    desensitize_func = desensitize_phone


class EmailFilter(SensitiveInfoFilter):
    desensitize_func = desensitize_email
