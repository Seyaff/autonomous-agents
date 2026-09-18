import re
import io
import json
import logging
from typing import List, Dict, Any, Optional
from pypdf import PdfReader
from app.config import settings

logger = logging.getLogger(__name__)

class MenuParserService:
    """Service to parse restaurant menu files (PDFs, text dumps, or images) into structured catalog items."""

    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """Extract plain text from PDF bytes using pypdf."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text.append(text)
        return "\n".join(full_text)

    async def parse_menu_content(self, text_content: str) -> List[Dict[str, Any]]:
        """Parse raw text into structured categories and menu items using LLM or rule-based fallback."""
        # If Gemini API key is available, use LLM structured extraction
        if settings.GOOGLE_API_KEY:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.0
                )
                prompt = (
                    "You are an expert restaurant catalog ingestion AI. Extract all menu items, "
                    "categories, prices, descriptions, and dietary badges from this text.\n"
                    "Output ONLY a valid JSON list of categories with items in this format:\n"
                    "[\n"
                    "  {\n"
                    '    "category_name": "Pizzas",\n'
                    '    "items": [\n'
                    '      {\n'
                    '        "name": "Margherita",\n'
                    '        "description": "Tomato sauce, fresh mozzarella, basil",\n'
                    '        "price": 14.50,\n'
                    '        "allergens": ["dairy", "gluten"],\n'
                    '        "is_available": true\n'
                    "      }\n"
                    "    ]\n"
                    "  }\n"
                    "]\n\n"
                    f"Menu Content:\n{text_content[:8000]}"
                )
                response = await llm.ainvoke(prompt)
                raw_json = response.content.strip()
                if "```json" in raw_json:
                    raw_json = raw_json.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_json:
                    raw_json = raw_json.split("```")[1].split("```")[0].strip()
                return json.loads(raw_json)
            except Exception as e:
                logger.warning(f"LLM menu parsing failed, using rule-based parser: {e}")

        # Rule-based fallback parser
        return self._fallback_regex_parser(text_content)

    def _fallback_regex_parser(self, text: str) -> List[Dict[str, Any]]:
        """Fallback rule-based parser that handles common menu formatting like 'Item Name - $12.99 - Description'."""
        lines = text.strip().split("\n")
        current_category = "Main Menu"
        categories: Dict[str, List[Dict[str, Any]]] = {current_category: []}

        # Match price pattern: $12.99 or 12.99 or 12$
        price_regex = re.compile(r"(\$?\s*(\d+(\.\d{1,2})?)\s*\$?)")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line looks like a category header (all caps or short without numbers)
            if len(line) < 40 and not price_regex.search(line) and (line.isupper() or line.endswith(":")):
                current_category = line.rstrip(":").title()
                if current_category not in categories:
                    categories[current_category] = []
                continue

            match = price_regex.search(line)
            if match:
                price_str = match.group(2)
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0

                # Split name and description
                parts = re.split(r"[-–—|]", line)
                name = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""

                # Clean name of any remaining price symbols
                name = price_regex.sub("", name).strip()

                if name:
                    categories[current_category].append({
                        "name": name,
                        "description": description,
                        "price": price,
                        "allergens": [],
                        "is_available": True
                    })

        # Format output
        result = []
        for cat_name, items in categories.items():
            if items:
                result.append({"category_name": cat_name, "items": items})
        return result

menu_parser_service = MenuParserService()
