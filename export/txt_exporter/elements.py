from ast import literal_eval
from functools import lru_cache
from json import loads
from functools import lru_cache
from xml.etree.ElementTree import fromstring

from humanize import naturalsize
from unicodedata import category

from emojis import emojis

__all__ = [
    "Text",
    "Image",
    "File",
    "Voice",
    "Video",
    "Emoji",
    "Notice",
    "RedPacket",
    "Application",
    "Call",
    "Feed",
]


def get_crc64(raw_str):
    _crc64_table = [0] * 256
    for i in range(256):
        bf = i
        for _ in range(8):
            bf = bf >> 1 ^ -7661587058870466123 if bf & 1 else bf >> 1
        _crc64_table[i] = bf
    v = -1
    for char in raw_str:
        value = _crc64_table[(ord(char) ^ v) & 255] ^ v >> 8
    return value


@lru_cache(maxsize=1024)
def get_cached_img_path(
    is_original: bool,
    md5HexStr: str,
):
    folder = "chatraw" if is_original else "chatimg"
    raw_str = f"{folder}:{md5HexStr}"
    crc64 = get_crc64(raw_str)
    file_name = f"Cache_{crc64:x}"

    return f"/{folder}/{file_name[-3:]}/{file_name}"


def readable_file_size(file_size):
    """
    Returns a human-readable file size.
    """
    return naturalsize(file_size, binary=True, format="%.2f") if file_size else None


class Text:
    def __init__(self, element):
        self.text = element.text

        self.content = self._get_content()

    def _get_content(self):
        return "[文本]", self.text


class Image:
    def __init__(self, element):
        self.text = element.imageText
        self.file_name = element.fileName
        self.readable_size = readable_file_size(element.fileSize)
        self.file_path = element.imageFilePath
        self.file_url = element.imageUrlOrigin

        self.cache_path = self._get_cache_path(element.original, element.md5HexStr.hex().upper())

        self.content = self._get_content()

    @staticmethod
    @lru_cache(maxsize=4096)
    def _get_cache_path(original, md5HexStr):
        def crc64(raw_str):
            _crc64_table = [0] * 256
            for i in range(256):
                bf = i
                for _ in range(8):
                    bf = bf >> 1 ^ -7661587058870466123 if bf & 1 else bf >> 1
                _crc64_table[i] = bf
            value = -1
            for char in raw_str:
                value = _crc64_table[(ord(char) ^ value) & 255] ^ value >> 8
            return value

        # original == 0 指未发原图，图片存于chatraw
        # original == 1 指发送原图，压缩后的图片存于chatimg,下载后原图存于chatraw
        folder = "chatimg" if original else "chatraw"
        raw_str = f"{folder}:{md5HexStr}"
        crc64_value = crc64(raw_str)
        file_name = f"Cache_{crc64_value:x}"

        return f"/{folder}/{file_name[-3:]}/{file_name}"

    def _get_content(self):
        return "[图片]", "\n".join(
            part
            for part in [
                f"{self.text}{self.cache_path} {self.readable_size}",
                self.file_path,
                self.file_url,
            ]
            if part
        )


class File:
    def __init__(self, element):
        self.file_name = element.fileName
        self.readable_size = readable_file_size(element.fileSize)

        self.content = self._get_content()

    def _get_content(self):
        return "[文件]", f"{self.file_name} {self.readable_size}"


class Voice:
    def __init__(self, element):
        self.voice_text = element.voiceText
        self.voice_len = element.voiceLen
        self.file_name = element.fileName
        self.readable_size = readable_file_size(element.fileSize)

        self.content = self._get_content()

    def _get_content(self):
        return "[语音]", "\n".join(
            part for part in [
                f"{self.voice_len}″ {self.voice_text}",
                self.file_name,
                self.readable_size
            ] if part
        )


class Video:
    def __init__(self, element):
        self.formated_video_len = self._seconds_to_hms(element.videoLen)
        self.file_name = element.fileName
        self.readable_size = readable_file_size(element.fileSize)
        self.path = element.videoPath

        self.content = self._get_content()

    @staticmethod
    def _seconds_to_hms(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def _get_content(self):
        return "[视频]", "\n".join(
            part for part in [
                f"{self.formated_video_len} {self.file_name} {self.readable_size}",
                self.path
            ] if part
        )


class Emoji:
    def __init__(self, element):
        self.emoji_id = element.emojiId
        self.text = element.emojiText

        self.content = self._get_content()

    def _get_content(self):
        if not self.text:
            self.text = emojis.get(self.emoji_id, "未知表情")
        return "[表情]", f"{self.text}-{self.emoji_id}"


class Notice:
    def __init__(self, element):
        self.info = element.noticeInfo
        self.info2 = element.noticeInfo2

        self.content = self._get_content()

    def _get_content(self):
        if not self.info and not self.info2:
            return "[提示]", None
        elif self.info:

            self.info = self.info.replace(r'\/', '/').replace('\u3000', ' ')
            self.info = ''.join(char for char in self.info if category(char) not in ('Cf', 'Cc'))

            root = fromstring(self.info)
            texts = [
                elem.get('txt')
                for elem in root.findall('.//nor')
                if elem.get('txt')
            ]
        elif self.info2:
            info2_dict = literal_eval(self.info2.replace(r"\/", "/"))
            texts = [item.get("txt", "")
                     for item
                     in info2_dict["items"]]

        return "[提示]", " ".join(texts)


class RedPacket:
    def __init__(self, element):
        self.prompt = element.redPacket.prompt
        self.summary = element.redPacket.summary

        self.content = self._get_content()

    def _get_content(self):
        return "[红包]", f"{self.summary} {self.prompt}"


class Application:
    def __init__(self, element):
        self.raw = element.applicationMessage

        self.content = self._get_content()

    def _get_content(self):
        return "[应用消息]", loads(self.raw)["prompt"]


class Call:
    def __init__(self, element):
        self.status = element.callStatus
        self.text = element.callText

        self.content = self._get_content()

    def _get_content(self):
        return "[通话]", f"{self.status}-{self.text}"


class Feed:
    def __init__(self, element):
        self.title = element.feedTitle.text
        self.feed_content = element.feedContent.text
        self.url = element.feedUrl

        self.content = self._get_content()

    def _get_content(self):
        return "[动态消息]", "\n".join(
            part for part in [
                self.title,
                self.feed_content,
                self.url
            ] if part
        )
