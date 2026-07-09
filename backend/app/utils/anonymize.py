"""
数据脱敏工具类
实现手机号、姓名、身份证、地址等敏感数据自动掩码处理
"""
import re
import hashlib
from loguru import logger


class AnonymizeUtil:
    """数据脱敏工具类"""
    
    # 默认掩码字符
    DEFAULT_MASK_CHAR = "*"
    
    @staticmethod
    def anonymize_name(name: str, preserve_prefix: int = 1, preserve_suffix: int = 0) -> str:
        """
        姓名脱敏处理
        
        Args:
            name: 原始姓名
            preserve_prefix: 保留前缀字符数（默认保留第一个字）
            preserve_suffix: 保留后缀字符数
            
        Returns:
            脱敏后的姓名，如：张**
        """
        if not name or len(name) < preserve_prefix + preserve_suffix + 1:
            return name
        
        prefix = name[:preserve_prefix]
        suffix = name[-preserve_suffix:] if preserve_suffix > 0 else ""
        middle_len = len(name) - preserve_prefix - preserve_suffix
        masked_middle = AnonymizeUtil.DEFAULT_MASK_CHAR * middle_len
        
        return prefix + masked_middle + suffix
    
    @staticmethod
    def anonymize_phone(phone: str, preserve_prefix: int = 3, preserve_suffix: int = 4) -> str:
        """
        手机号脱敏处理
        
        Args:
            phone: 原始手机号
            preserve_prefix: 保留前缀位数（默认保留前3位）
            preserve_suffix: 保留后缀位数（默认保留后4位）
            
        Returns:
            脱敏后的手机号，如：138****5678
        """
        if not phone or len(phone) < preserve_prefix + preserve_suffix + 1:
            return phone
        
        # 移除可能的非数字字符
        clean_phone = re.sub(r'[^\d]', '', phone)
        
        if len(clean_phone) != 11:
            logger.warning(f"手机号格式异常: length={len(phone)}")
            return AnonymizeUtil.DEFAULT_MASK_CHAR * len(clean_phone)
        
        prefix = clean_phone[:preserve_prefix]
        suffix = clean_phone[-preserve_suffix:]
        masked_middle = AnonymizeUtil.DEFAULT_MASK_CHAR * (11 - preserve_prefix - preserve_suffix)
        
        return prefix + masked_middle + suffix
    
    @staticmethod
    def anonymize_id_card(id_card: str, preserve_prefix: int = 6, preserve_suffix: int = 4) -> str:
        """
        身份证号脱敏处理
        
        Args:
            id_card: 原始身份证号
            preserve_prefix: 保留前缀位数（默认保留前6位）
            preserve_suffix: 保留后缀位数（默认保留后4位）
            
        Returns:
            脱敏后的身份证号，如：310101********1234
        """
        if not id_card:
            return id_card
        
        # 移除可能的非数字字符（身份证最后可能是X）
        clean_id = re.sub(r'[^\dXx]', '', id_card.upper())
        
        if len(clean_id) != 18:
            logger.warning(f"身份证号格式异常: length={len(id_card)}")
            return AnonymizeUtil.DEFAULT_MASK_CHAR * len(clean_id)
        
        prefix = clean_id[:preserve_prefix]
        suffix = clean_id[-preserve_suffix:]
        masked_middle = AnonymizeUtil.DEFAULT_MASK_CHAR * (18 - preserve_prefix - preserve_suffix)
        
        return prefix + masked_middle + suffix
    
    @staticmethod
    def anonymize_email(email: str, preserve_prefix_len: int = 3) -> str:
        """
        邮箱地址脱敏处理
        
        Args:
            email: 原始邮箱地址
            preserve_prefix_len: 保留前缀字符数
            
        Returns:
            脱敏后的邮箱地址，如：zha***@company.com
        """
        if not email or '@' not in email:
            return email
        
        username, domain = email.split('@')
        
        if len(username) <= preserve_prefix_len:
            preserve_prefix_len = len(username) // 2
        
        prefix = username[:preserve_prefix_len]
        masked_len = len(username) - preserve_prefix_len
        masked_middle = AnonymizeUtil.DEFAULT_MASK_CHAR * masked_len
        
        return prefix + masked_middle + '@' + domain
    
    @staticmethod
    def anonymize_address(address: str, preserve_len: int = 10) -> str:
        """
        地址脱敏处理
        
        Args:
            address: 原始地址
            preserve_len: 保留前缀长度
            
        Returns:
            脱敏后的地址，如：上海市浦东新区***
        """
        if not address or len(address) <= preserve_len:
            return address
        
        prefix = address[:preserve_len]
        masked_suffix = AnonymizeUtil.DEFAULT_MASK_CHAR * 3
        
        return prefix + masked_suffix
    
    @staticmethod
    def anonymize_company(company: str, preserve_len: int = 4) -> str:
        """
        企业名称脱敏处理
        
        Args:
            company: 原始企业名称
            preserve_len: 保留前缀长度
            
        Returns:
            脱敏后的企业名称
        """
        if not company or len(company) <= preserve_len:
            return company
        
        prefix = company[:preserve_len]
        masked_suffix = AnonymizeUtil.DEFAULT_MASK_CHAR * 3
        
        return prefix + masked_suffix
    
    @staticmethod
    def hash_data(data: str, algorithm: str = "sha256") -> str:
        """
        数据哈希处理
        
        Args:
            data: 原始数据
            algorithm: 哈希算法（md5/sha256）
            
        Returns:
            哈希后的字符串
        """
        if not data:
            return ""
        
        if algorithm == "md5":
            return hashlib.md5(data.encode(), usedforsecurity=False).hexdigest()
        elif algorithm == "sha256":
            return hashlib.sha256(data.encode()).hexdigest()
        else:
            return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def anonymize_by_type(data: str, data_type: str) -> str:
        """
        根据数据类型自动选择脱敏方法
        
        Args:
            data: 原始数据
            data_type: 数据类型(name/phone/id_card/email/address/company)
            
        Returns:
            脱敏后的数据
        """
        anonymize_methods = {
            "name": AnonymizeUtil.anonymize_name,
            "phone": AnonymizeUtil.anonymize_phone,
            "id_card": AnonymizeUtil.anonymize_id_card,
            "email": AnonymizeUtil.anonymize_email,
            "address": AnonymizeUtil.anonymize_address,
            "company": AnonymizeUtil.anonymize_company,
        }
        
        method = anonymize_methods.get(data_type)
        if method:
            return method(data)
        
        # 默认返回原始数据
        logger.warning(f"未知的脱敏类型: {data_type}")
        return data
    
    @staticmethod
    def batch_anonymize(data_dict: dict, rules: dict) -> dict:
        """
        批量脱敏处理
        
        Args:
            data_dict: 包含多个字段的原始数据字典
            rules: 脱敏规则字典，格式为 {字段名: 数据类型}
            
        Returns:
            脱敏后的数据字典
        """
        result = {}
        for field, value in data_dict.items():
            if field in rules and isinstance(value, str):
                result[field] = AnonymizeUtil.anonymize_by_type(value, rules[field])
            else:
                result[field] = value
        
        return result