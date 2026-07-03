"""Web-Crawler: URLs indexieren für RAG.

Nutzt requests + BeautifulSoup für HTML-Parsing.
Respektiert robots.txt und rate-limiting.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


DEFAULT_USER_AGENT = "ConText/0.3 (+https://github.com/Tabtii/context-engineer)"
DEFAULT_TIMEOUT = 30


@dataclass
class CrawlResult:
    url: str
    content: str
    title: str
    links: list[str]
    status_code: int
    error: Optional[str] = None


class WebCrawler:
    """Polite Web-Crawler mit robots.txt-Support."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
        max_size_mb: float = 5.0,
        respect_robots: bool = True,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.respect_robots = respect_robots
        self._robots_cache: dict[str, RobotFileParser] = {}

    def fetch(self, url: str) -> CrawlResult:
        """Hole einzelne URL."""
        if self.respect_robots and not self._allowed(url):
            return CrawlResult(
                url=url, content="", title="", links=[],
                status_code=0, error="Blocked by robots.txt",
            )
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
                stream=True,  # um max_size zu checken
            )
            resp.raise_for_status()
            # Check Content-Length
            content_length = int(resp.headers.get("Content-Length", 0))
            if content_length > self.max_size_bytes:
                return CrawlResult(
                    url=url, content="", title="", links=[],
                    status_code=resp.status_code,
                    error=f"Content too large: {content_length} bytes",
                )
            content = resp.text
            if len(content) > self.max_size_bytes:
                content = content[: self.max_size_bytes]
        except requests.exceptions.RequestException as e:
            return CrawlResult(
                url=url, content="", title="", links=[],
                status_code=0, error=str(e),
            )
        # Parse HTML
        soup = BeautifulSoup(content, "html.parser")
        title = soup.title.string if soup.title else ""
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        # Extract main text
        text = soup.get_text(separator="\n", strip=True)
        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Extract links
        links = []
        parsed_base = urlparse(url)
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            full_url = urljoin(url, href)
            # Only same-domain links
            if urlparse(full_url).netloc == parsed_base.netloc:
                links.append(full_url)
        return CrawlResult(
            url=url,
            content=text,
            title=title.strip() if title else "",
            links=list(set(links)),
            status_code=resp.status_code,
        )

    def crawl(
        self,
        start_url: str,
        max_pages: int = 10,
        same_domain_only: bool = True,
    ) -> list[CrawlResult]:
        """BFS-Crawl ab start_url."""
        visited: set[str] = set()
        queue: list[str] = [start_url]
        results: list[CrawlResult] = []
        while queue and len(results) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            result = self.fetch(url)
            if result.error:
                continue
            results.append(result)
            # Add new links
            for link in result.links:
                if link not in visited:
                    queue.append(link)
        return results

    def _allowed(self, url: str) -> bool:
        """Check robots.txt."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url not in self._robots_cache:
            rp: Optional[RobotFileParser] = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                # If robots.txt unreachable, be conservative
                rp = None
            self._robots_cache[robots_url] = rp  # type: ignore[assignment]
        rp = self._robots_cache[robots_url]
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)


def html_to_text(html: str) -> str:
    """Schnelle HTML-zu-Text-Konvertierung ohne Crawler-Setup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)
