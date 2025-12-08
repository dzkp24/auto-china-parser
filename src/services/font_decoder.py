import io
import hashlib
from fontTools.ttLib import TTFont
from loguru import logger

class FontDecoder:
    KNOWN_HASHES = {
        # Пример: "d41d8cd98f00b204e9800998ecf8427e": "5",
    }

    def _get_glyph_hash(self, font: TTFont, glyph_name: str) -> str:
        try:
            glyph = font['glyf'][glyph_name]
            if not hasattr(glyph, 'coordinates'):
                return "empty"
            coords = list(glyph.coordinates)
            return hashlib.md5(str(coords).encode('utf-8')).hexdigest()
        except Exception:
            return "error"

    def decode(self, font_bytes: bytes, obfuscated_text: str) -> str:
        if not font_bytes or not obfuscated_text:
            return obfuscated_text

        try:
            font = TTFont(io.BytesIO(font_bytes))
            cmap = font.getBestCmap()
            decoded_chars = []
            
            for char in obfuscated_text:
                char_code = ord(char)
                if char_code in cmap:
                    glyph_name = cmap[char_code]
                    glyph_hash = self._get_glyph_hash(font, glyph_name)
                    
                    if glyph_hash in self.KNOWN_HASHES:
                        decoded_chars.append(self.KNOWN_HASHES[glyph_hash])
                    else:
                        logger.warning(f"UNKNOWN FONT GLYPH: {char} -> Hash: {glyph_hash}")
                        decoded_chars.append(f"[{glyph_hash[:4]}]") 
                else:
                    decoded_chars.append(char)
            return "".join(decoded_chars)
        except Exception as e:
            logger.error(f"Font decode error: {e}")
            return obfuscated_text