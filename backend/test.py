from utils.html_utils import clean_html, clean_and_format_html
from utils.markdown_utils import strip_image_links, strip_javascript_links
from core.crawler import PlaywrightCrawler
import asyncio


urls = [
    "https://www.csdn.net/",
    "https://hub.baai.ac.cn/",
    "https://edition.cnn.com/",
    "https://paperswithcode.com/",
]


async def main():
    # Use PlaywrightCrawler as an async context manager
    async with PlaywrightCrawler() as crawler:
        i = 0
        async for result in crawler.process_urls(urls):
            if result.get("error"):
                print(f"Error fetching {result['original_url']}: {result['error']}")
                continue

            html_content = result["content"]
            if not html_content:
                print(f"No content fetched for {result['original_url']}")
                continue

            print(f"Successfully fetched {result['final_url']}. Cleaning HTML...")
            cleaned_markdown = clean_and_format_html(
                html_content, result["original_url"], "markdown"
            )

            cleaned_markdown = strip_image_links(cleaned_markdown)
            cleaned_markdown = strip_javascript_links(cleaned_markdown)

            if cleaned_markdown:
                filename = f"example_test_{i}.txt"
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(cleaned_markdown)
                    print(f"Saved {filename}")
                except Exception as e:
                    print(f"Error writing file {filename}: {e}")
            else:
                print(f"No cleaned HTML to save for {result['original_url']}")
            i += 1
    print("Crawler finished and shutdown.")


if __name__ == "__main__":
    asyncio.run(main())
