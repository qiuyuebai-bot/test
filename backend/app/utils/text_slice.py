"""
文本分段切片工具
简化版本，不依赖jieba
"""
import re
from typing import List, Dict, Any


class TextSliceUtil:
    """
    文本分段切片工具类
    支持按段落、语义、章节等多种切片方式
    """
    
    # 最大切片长度
    MAX_SLICE_LENGTH = 2000
    
    # 最小切片长度
    MIN_SLICE_LENGTH = 100
    
    @classmethod
    def slice_by_paragraph(
        cls,
        text: str,
        max_length: int = None,
        overlap: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        按段落切片
        
        Args:
            text: 待切片文本
            max_length: 最大切片长度
            overlap: 重叠字符数
            
        Returns:
            切片列表，每项包含 content, index, word_count
        """
        max_length = max_length or cls.MAX_SLICE_LENGTH
        
        # 按换行符分割段落
        paragraphs = text.split('\n')
        slices = []
        current_slice = []
        current_length = 0
        slice_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_length = len(para)
            
            # 如果单个段落超过最大长度，继续分割
            if para_length > max_length:
                # 保存当前切片
                if current_slice:
                    content = '\n'.join(current_slice)
                    slices.append({
                        'content': content,
                        'index': slice_index,
                        'word_count': len(content),
                        'slice_type': 'paragraph',
                    })
                    slice_index += 1
                    current_slice = []
                    current_length = 0
                
                # 分割长段落
                sub_slices = cls._split_long_paragraph(para, max_length, overlap)
                for sub in sub_slices:
                    slices.append({
                        'content': sub,
                        'index': slice_index,
                        'word_count': len(sub),
                        'slice_type': 'paragraph_split',
                    })
                    slice_index += 1
            
            # 如果加上当前段落会超过最大长度，先保存当前切片
            elif current_length + para_length > max_length:
                if current_slice:
                    content = '\n'.join(current_slice)
                    slices.append({
                        'content': content,
                        'index': slice_index,
                        'word_count': len(content),
                        'slice_type': 'paragraph',
                    })
                    slice_index += 1
                    current_slice = []
                    current_length = 0
            
            # 添加当前段落
            current_slice.append(para)
            current_length += para_length
        
        # 保存最后一个切片
        if current_slice:
            content = '\n'.join(current_slice)
            slices.append({
                'content': content,
                'index': slice_index,
                'word_count': len(content),
                'slice_type': 'paragraph',
            })
        
        return slices if slices else [{'content': text, 'index': 0, 'word_count': len(text), 'slice_type': 'full'}]
    
    @classmethod
    def slice_by_semantic(
        cls,
        text: str,
        max_length: int = None,
    ) -> List[Dict[str, Any]]:
        """
        按语义边界切片（基于句子分割）
        
        Args:
            text: 待切片文本
            max_length: 最大切片长度
            
        Returns:
            切片列表
        """
        max_length = max_length or cls.MAX_SLICE_LENGTH
        
        # 按句子分割（中文常用标点）
        sentences = re.split(r'[。！？；\n]+', text)
        
        slices = []
        current_sentences = []
        current_length = 0
        slice_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_length = len(sentence)
            
            # 如果单个句子超长
            if sentence_length > max_length:
                if current_sentences:
                    content = '。'.join(current_sentences) + '。'
                    slices.append({
                        'content': content,
                        'index': slice_index,
                        'word_count': len(content),
                        'slice_type': 'semantic',
                    })
                    slice_index += 1
                    current_sentences = []
                    current_length = 0
                
                # 分割长句
                sub_slices = cls._split_long_paragraph(sentence, max_length, 0)
                for sub in sub_slices:
                    slices.append({
                        'content': sub,
                        'index': slice_index,
                        'word_count': len(sub),
                        'slice_type': 'sentence_split',
                    })
                    slice_index += 1
                continue

            # 如果加上当前句子会超长
            elif current_length + sentence_length > max_length:
                if current_sentences:
                    content = '。'.join(current_sentences) + '。'
                    slices.append({
                        'content': content,
                        'index': slice_index,
                        'word_count': len(content),
                        'slice_type': 'semantic',
                    })
                    slice_index += 1
                    current_sentences = []
                    current_length = 0
            
            current_sentences.append(sentence)
            current_length += sentence_length
        
        # 保存最后一个切片
        if current_sentences:
            content = '。'.join(current_sentences)
            if not content.endswith('。'):
                content += '。'
            slices.append({
                'content': content,
                'index': slice_index,
                'word_count': len(content),
                'slice_type': 'semantic',
            })
        
        return slices if slices else [{'content': text, 'index': 0, 'word_count': len(text), 'slice_type': 'full'}]
    
    @classmethod
    def slice_by_section(
        cls,
        text: str,
        section_markers: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        按章节标记切片
        
        Args:
            text: 待切片文本
            section_markers: 章节标题标记列表
            
        Returns:
            切片列表
        """
        if section_markers is None:
            section_markers = ['#', '##', '###', '一、', '二、', '三、', '（一）', '（二）']
        
        slices = []
        lines = text.split('\n')
        current_section = []
        current_title = ''
        slice_index = 0
        
        for line in lines:
            line = line.strip()
            
            # 检查是否是章节标题
            is_section_start = any(line.startswith(marker) for marker in section_markers)
            
            if is_section_start and current_section:
                # 保存当前章节
                content = '\n'.join(current_section)
                slices.append({
                    'content': content,
                    'index': slice_index,
                    'word_count': len(content),
                    'title': current_title or f'章节{slice_index + 1}',
                    'slice_type': 'section',
                })
                slice_index += 1
                current_section = []
                current_title = ''
            
            current_section.append(line)
            if is_section_start and not current_title:
                current_title = line.strip('#').strip()
        
        # 保存最后一个章节
        if current_section:
            content = '\n'.join(current_section)
            slices.append({
                'content': content,
                'index': slice_index,
                'word_count': len(content),
                'title': current_title or f'章节{slice_index + 1}',
                'slice_type': 'section',
            })
        
        return slices if slices else [{'content': text, 'index': 0, 'word_count': len(text), 'slice_type': 'full'}]
    
    @classmethod
    def extract_keywords(
        cls,
        text: str,
        top_k: int = 10,
    ) -> List[str]:
        """
        提取关键词（简化版本）
        
        Args:
            text: 待处理文本
            top_k: 返回关键词数量
            
        Returns:
            关键词列表
        """
        # 移除常见停用词
        stopwords = {'的', '了', '是', '在', '和', '与', '或', '等', '以及', '对于', '关于', '通过', '为了', '一个', '这个', '那个'}
        
        # 简单分词（按标点和空格分割）
        words = re.split(r'[，。、；：！？\s\n]+', text)
        
        # 统计词频
        word_freq = {}
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按频率排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, _ in sorted_words[:top_k]]
    
    @classmethod
    def _split_long_paragraph(
        cls,
        text: str,
        max_length: int,
        overlap: int,
    ) -> List[str]:
        """
        分割超长段落
        
        Args:
            text: 待分割文本
            max_length: 最大长度
            overlap: 重叠字符数
            
        Returns:
            分割后的文本列表
        """
        if len(text) <= max_length:
            return [text]

        if overlap >= max_length:
            overlap = max_length // 2

        slices = []
        start = 0
        
        while start < len(text):
            end = start + max_length
            slice_text = text[start:end]
            
            # 尝试在句子边界分割
            if end < len(text):
                last_punct = max(
                    slice_text.rfind('。'),
                    slice_text.rfind('！'),
                    slice_text.rfind('？'),
                    slice_text.rfind('，'),
                )
                
                if last_punct > max_length * 0.7:
                    slice_text = slice_text[:last_punct + 1]
                    end = start + last_punct + 1
            
            slices.append(slice_text)
            start = end - overlap if overlap > 0 else end
        
        return slices

    @classmethod
    def _hash_content(cls, content: str) -> str:
        """
        计算内容哈希
        
        Args:
            content: 内容文本
            
        Returns:
            MD5哈希值
        """
        import hashlib
        return hashlib.md5(content.encode('utf-8')).hexdigest()
