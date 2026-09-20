import json
from typing import Optional, Union

from aiohttp import ClientSession, ClientTimeout

import core.boosty.defs as cdefs
from core.defs.common import AuthToken
from core.logger import setup_logger

logger = setup_logger()


def _first_text_line(content: str) -> str:
    """The plain text of a Boosty text block, which is a draft.js JSON array."""
    try:
        return str(json.loads(content)[0]).strip().strip("*").strip()
    except Exception:
        return ""


class BoostyClient:

    def __init__(
        self,
        chunk_size: int,
        download_timeout: int,
        auth_token: Optional[AuthToken] = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.download_timeout = download_timeout
        self.base_url = "https://api.boosty.to"
        self._base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",  # noqa: E501
            "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        self.auth_token = auth_token

    def _get_headers(self) -> dict:
        if self.auth_token:
            return {
                **self._base_headers,
                "Authorization": f"Bearer {self.auth_token.authorization}",
                "Cookie": self.auth_token.cookie,
            }
        return self._base_headers

    def get_client_session(self) -> ClientSession:
        return ClientSession(
            headers=self._get_headers(),
            timeout=ClientTimeout(total=self.download_timeout),
        )

    def _wrap_media_item(self, media: dict) -> Union[
        cdefs.BoostyImageDto,
        cdefs.BoostyVideoDto,
        cdefs.BoostyAudioDto,
        cdefs.BoostyFileDto,
        cdefs.BoostyTextDto,
        cdefs.BoostyLinkDto,
        cdefs.BoostyListDto,
        None,
    ]:
        match media["type"]:
            case cdefs.BoostyMediaType.IMAGE.value:
                if "width" not in media:  # issues/30 "узкая" картинка
                    return None
                return cdefs.BoostyImageDto(
                    id=media["id"],
                    url=media["url"],
                    width=media["width"],
                    height=media["height"],
                    size=media["size"],
                )
            case cdefs.BoostyMediaType.VIDEO.value:
                video = cdefs.BoostyVideoDto(id=media["id"], title=media["title"])
                for url in media["playerUrls"]:
                    if url["url"] != "" and url["type"] in cdefs.VIDEO_QUALITY_GRADE:
                        size = cdefs.BoostyVideoSizesType(url["type"])
                        video.player_urls[size] = cdefs.BoostyPlayerUrlDto(
                            url=url["url"],
                            size=size,
                        )
                return video
            case cdefs.BoostyMediaType.AUDIO.value:
                return cdefs.BoostyAudioDto(
                    id=media["id"],
                    url=media["url"],
                    size=media["size"],
                    title=media["title"],
                )
            case cdefs.BoostyMediaType.FILE.value:
                return cdefs.BoostyFileDto(
                    id=media["id"],
                    url=media["url"],
                    size=media["size"],
                    title=media["title"],
                )
            case cdefs.BoostyMediaType.TEXT.value | cdefs.BoostyMediaType.HEADER.value:
                return cdefs.BoostyTextDto(
                    content=media["content"],
                    modificator=media["modificator"],
                )
            case cdefs.BoostyMediaType.LINK.value:
                return cdefs.BoostyLinkDto(
                    content=media["content"],
                    url=media["url"],
                )
            case cdefs.BoostyMediaType.LIST.value:
                return cdefs.BoostyListDto(
                    style=media["style"],
                    items=media["items"],
                )
        return None

    async def get_post_info(self, author: str, post_id: str) -> cdefs.BoostyPostDto:
        url = self.base_url + f"/v1/blog/{author}/post/{post_id}"
        async with self.get_client_session() as session:
            response = await session.get(url)
            response.raise_for_status()
            content = await response.json()

        text_content = cdefs.BoostyPostTextDto()
        result = cdefs.BoostyPostDto(
            has_access=content["hasAccess"],
            id=content["id"],
            int_id=content["intId"],
            title=content["title"],
            publish_time=content["publishTime"],
            signed_query=content["signedQuery"],
        )

        self._fill_post_blocks(result, content["data"])
        return result

    def _fill_post_blocks(self, post: cdefs.BoostyPostDto, blocks: list) -> None:
        """Split the post body into text and attachments.

        The text an author writes above an attachment is its name, so it is
        carried over to the attachment instead of being dropped.
        """
        text_content = cdefs.BoostyPostTextDto()
        pending_headings: list[str] = []

        for block in blocks:
            wrapped = self._wrap_media_item(block)
            if not wrapped:
                continue
            if isinstance(
                wrapped,
                (cdefs.BoostyTextDto, cdefs.BoostyLinkDto, cdefs.BoostyListDto),
            ):
                text_content.content.append(wrapped)
                if isinstance(wrapped, cdefs.BoostyTextDto):
                    if line := _first_text_line(wrapped.content):
                        pending_headings.append(line)
                continue
            wrapped.heading_lines = pending_headings
            pending_headings = []
            post.media.append(wrapped)

        post.text_content = text_content

    async def get_posts_list(
        self,
        author: str,
        limit: int = 20,
        offset: Optional[str] = None,
    ) -> cdefs.BoostyPostsListDto:
        params = {
            "limit": limit,
            "reply_limit": 0,
            "comments_limit": 0,
        }
        if offset:
            params["offset"] = offset
        url = self.base_url + f"/v1/blog/{author}/post/"
        async with self.get_client_session() as session:
            response = await session.get(url, params=params)
            response.raise_for_status()
            content = await response.json()
        content_extra = content["extra"]
        content_data = content["data"]
        result = cdefs.BoostyPostsListDto(
            cdefs.BoostyExtraDto(
                is_last=content_extra["isLast"],
                offset=content_extra["offset"],
            )
        )
        for post in content_data:
            new_post = cdefs.BoostyPostDto(
                has_access=post["hasAccess"],
                id=post["id"],
                int_id=post["intId"],
                title=post["title"],
                publish_time=post["publishTime"],
                signed_query=post["signedQuery"],
            )
            self._fill_post_blocks(new_post, post["data"])
            result.data.append(new_post)
        return result

    async def get_max_int_id(self, author: str) -> Optional[int]:
        try:
            post_list = await self.get_posts_list(author, limit=1)
            if not post_list.have_posts():
                return None
            post = post_list.data[0]
            return post.int_id
        except Exception as e:
            logger.error(e)
            return None
