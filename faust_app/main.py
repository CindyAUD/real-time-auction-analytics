import asyncio
import logging
from app.consumer import run

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    print("🚀 Starting Auction Processor...")
    asyncio.run(run())
