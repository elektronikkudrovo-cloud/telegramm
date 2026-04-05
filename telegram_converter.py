#!/usr/bin/env python3
"""
Telegram Export to Obsidian Converter

Converts Telegram desktop export (JSON) to Obsidian vault with proper Markdown formatting.
Supports media files, text entities, and message threading.
"""

import argparse
import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ijson

from config import (
    CACHE_MAX_SIZE,
    DEFAULT_CHAT_NAME,
    DEFAULT_SENDER,
    DEFAULT_TIME,
    MAX_SEARCH_INDEX_SAMPLE,
    MEDIA_KEYS,
    DATE_FORMAT,
    TIME_FORMAT,
)
from utils import escape_md, hash_file, sanitize_filename, setup_logger


class TelegramObsidianConverter:
    """Convert Telegram exports to Obsidian vault format."""
    
    def __init__(self, export_path: str, output_path: str):
        """Initialize converter with export and output paths."""
        self.export_root = Path(export_path)
        self.vault_root = Path(output_path)
        self.media_index: Dict[str, Path] = {}
        self.media_hashes: Dict[str, str] = {}  # hash -> filename
        self.message_index: Dict[int, str] = {}
        self.search_index: List[Dict] = []
        
        # Validate paths
        if not self.export_root.exists():
            raise FileNotFoundError(f"Export path does not exist: {export_path}")
    
    def build_media_index(self) -> None:
        """Build index of all media files in export directory."""
        logging.info("Scanning media files...")
        count = 0
        
        try:
            for file in self.export_root.rglob('*'):
                if file.is_file() and not file.name.startswith('.'):
                    try:
                        rel_path = str(file.relative_to(self.export_root))
                        self.media_index[rel_path] = file
                        self.media_index[file.name] = file
                        count += 1
                    except Exception as e:
                        logging.warning(f"Failed to index file {file}: {e}")
            
            logging.info(f"✓ Indexed {count} media files")
        except Exception as e:
            logging.error(f"Failed to build media index: {e}")
            raise
    
    def find_media(self, file_path: str) -> Optional[Path]:
        """Find media file by path or name."""
        if not file_path:
            return None
        
        # Try exact path first
        if file_path in self.media_index:
            return self.media_index[file_path]
        
        # Try filename only
        name = Path(file_path).name
        return self.media_index.get(name)
    
    def copy_media(self, src: Path, dst_folder: Path) -> Optional[str]:
        """Copy media file to destination folder, handling duplicates."""
        if not src.exists():
            logging.warning(f"Media file does not exist: {src}")
            return None
        
        try:
            file_hash = hash_file(src)
            
            if not file_hash:
                logging.warning(f"Failed to hash file: {src.name}")
                return None
            
            # Check if file already copied (deduplication)
            if file_hash in self.media_hashes:
                logging.debug(f"Using existing copy: {self.media_hashes[file_hash]}")
                return self.media_hashes[file_hash]
            
            # Create destination folder
            dst_folder.mkdir(parents=True, exist_ok=True)
            
            # Sanitize filename
            dst = dst_folder / sanitize_filename(src.name)
            
            # Handle file name conflicts
            counter = 1
            original_dst = dst
            while dst.exists():
                dst = dst_folder / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
                if counter > 1000:
                    logging.warning(f"Too many duplicates for {src.name}")
                    return None
            
            # Copy file preserving metadata
            import shutil
            shutil.copy2(src, dst)
            
            self.media_hashes[file_hash] = dst.name
            logging.debug(f"Copied media: {src.name} -> {dst.name}")
            return dst.name
            
        except Exception as e:
            logging.error(f"Failed to copy media {src.name}: {e}")
            return None
    
    @lru_cache(maxsize=CACHE_MAX_SIZE)
    def _utf16_to_offset(self, text: str, utf16_pos: int) -> int:
        """Convert UTF-16 offset to UTF-8 offset for correct text entity positioning."""
        if utf16_pos <= 0:
            return 0
        
        try:
            # Encode to UTF-16-LE (Telegram format)
            encoded = text.encode('utf-16-le')
            
            # Safety check
            if utf16_pos * 2 > len(encoded):
                return len(text)
            
            # Extract prefix and decode
            prefix = encoded[:utf16_pos * 2]
            decoded = prefix.decode('utf-16-le', errors='ignore')
            
            return len(decoded)
        
        except Exception as e:
            logging.warning(f"UTF-16 conversion failed: {e}")
            return utf16_pos
    
    def fix_entity_offsets(self, text: str, entities: List[Dict]) -> List[Dict]:
        """Fix entity offsets from UTF-16 to UTF-8 encoding."""
        if not entities:
            return []
        
        fixed = []
        
        try:
            for ent in entities:
                if not isinstance(ent, dict):
                    continue
                
                offset = ent.get('offset', 0)
                length = ent.get('length', 0)
                
                # Convert offsets
                new_start = self._utf16_to_offset(text, offset)
                new_end = self._utf16_to_offset(text, offset + length)
                new_len = new_end - new_start
                
                # Validate converted offsets
                if 0 <= new_start < len(text) and new_len > 0:
                    fixed.append({
                        **ent,
                        'offset': new_start,
                        'length': min(new_len, len(text) - new_start)
                    })
            
            # Sort by offset
            fixed.sort(key=lambda e: e['offset'])
            
        except Exception as e:
            logging.warning(f"Failed to fix entity offsets: {e}")
            return []
        
        return fixed
    
    def apply_entities(self, text: str, entities: List[Dict]) -> str:
        """Apply text formatting based on Telegram entities."""
        if not text:
            return ""
        
        if not entities:
            return escape_md(text)
        
        result = ""
        last_pos = 0
        
        try:
            for ent in entities:
                start = ent.get('offset', 0)
                end = start + ent.get('length', 0)
                
                # Add unformatted text before entity
                if start > last_pos:
                    result += escape_md(text[last_pos:start])
                
                # Extract and format segment
                segment = text[start:end]
                ent_type = ent.get('type', '')
                
                # Apply formatting
                if ent_type == 'bold':
                    result += f"**{escape_md(segment)}**"
                elif ent_type == 'italic':
                    result += f"*{escape_md(segment)}*"
                elif ent_type == 'code':
                    result += f"`{escape_md(segment)}`"
                elif ent_type == 'pre':
                    lang = ent.get('language', '')
                    result += f"```{lang}\n{segment}\n```"
                elif ent_type == 'text_link':
                    href = ent.get('href', '#')
                    result += f"[{escape_md(segment)}]({href})"
                elif ent_type == 'mention':
                    username = segment[1:] if segment.startswith('@') else segment
                    result += f"[@{escape_md(username)}](https://t.me/{username})"
                elif ent_type == 'underline':
                    result += f"<u>{escape_md(segment)}</u>"
                elif ent_type == 'strikethrough':
                    result += f"~~{escape_md(segment)}~~"
                elif ent_type == 'spoiler':
                    result += f"||{escape_md(segment)}||"
                else:
                    result += escape_md(segment)
                
                last_pos = end
            
            # Add remaining text
            if last_pos < len(text):
                result += escape_md(text[last_pos:])
        
        except Exception as e:
            logging.warning(f"Failed to apply entities: {e}")
            return escape_md(text)
        
        return result
    
    def entities_to_markdown(self, text: str, entities: List[Dict]) -> str:
        """Convert text with Telegram entities to Markdown."""
        if not text:
            return ""
        
        try:
            fixed_entities = self.fix_entity_offsets(text, entities)
            return self.apply_entities(text, fixed_entities)
        except Exception as e:
            logging.warning(f"Failed to convert entities to markdown: {e}")
            return escape_md(text)
    
    def process_message(self, msg: Dict, folder: Path, chat_name: str) -> Tuple[str, str]:
        """Process single message and convert to Markdown."""
        parts = []
        
        try:
            msg_id = msg.get('id')
            if not msg_id:
                return "", "unknown"
            
            # Store message reference
            self.message_index[msg_id] = f"[[{chat_name}#^{msg_id}]]"
            
            # Parse date and sender
            date = msg.get('date', '')
            sender = msg.get('from', DEFAULT_SENDER)
            
            try:
                dt = datetime.fromisoformat(date)
                time_str = dt.strftime(TIME_FORMAT)
                file_date = dt.strftime(DATE_FORMAT)
            except (ValueError, TypeError):
                time_str = DEFAULT_TIME
                file_date = "unknown"
            
            # Add message header
            parts.append(f"## ⏰ {time_str} — *{escape_md(str(sender))}* ^{msg_id}")
            
            # Add reply reference if exists
            if 'reply_to_message_id' in msg:
                rid = msg['reply_to_message_id']
                if rid in self.message_index:
                    parts.append(f"↩️ Reply to {self.message_index[rid]}")
            
            # Process text content
            text = msg.get('text', '')
            if isinstance(text, list):
                # Handle text as list of strings/objects
                text = ''.join([
                    t if isinstance(t, str) else t.get('text', '')
                    for t in text if t
                ])
            
            text = str(text) if text else ""
            
            # Apply text entities
            entities = msg.get('entities') or msg.get('text_entities') or []
            text_md = self.entities_to_markdown(text, entities)
            
            if text_md:
                parts.append(text_md)
            
            # Add to search index
            self.search_index.append({
                "chat": chat_name,
                "id": msg_id,
                "date": date,
                "text": text_md or text or "",
                "sender": str(sender),
                "has_media": any(key in msg for key in MEDIA_KEYS)
            })
            
            # Process media
            for key in MEDIA_KEYS:
                if key in msg and msg[key]:
                    media_path = msg[key]
                    src = self.find_media(str(media_path))
                    
                    if src:
                        copied = self.copy_media(src, folder)
                        if copied:
                            if key in ['photo', 'sticker']:
                                parts.append(f"![]({copied})")
                            else:
                                parts.append(f"[{key}]({copied})")
            
            return '\n'.join(parts), file_date
        
        except Exception as e:
            logging.error(f"Failed to process message {msg.get('id', 'unknown')}: {e}")
            return "", "unknown"
    
    def run(self) -> None:
        """Execute the conversion process."""
        try:
            # Create output directory
            self.vault_root.mkdir(parents=True, exist_ok=True)
            logging.info(f"📁 Output vault: {self.vault_root}")
            
            # Build media index
            self.build_media_index()
            
            # Check for export file
            json_path = self.export_root / 'result.json'
            if not json_path.exists():
                raise FileNotFoundError(f"result.json not found in {self.export_root}")
            
            logging.info("Processing chats...")
            index_lines = ["# Telegram Import Index\n", "## Chats\n"]
            total_messages = 0
            total_chats = 0
            
            # Process chats
            with open(json_path, 'rb') as f:
                chats = ijson.items(f, 'chats.item')
                
                for chat in chats:
                    try:
                        chat_name = sanitize_filename(
                            chat.get('name', str(chat.get('id', DEFAULT_CHAT_NAME)))
                        )
                        chat_folder = self.vault_root / chat_name
                        chat_folder.mkdir(parents=True, exist_ok=True)
                        
                        index_lines.append(f"- [[{chat_name}]]")
                        
                        messages = chat.get('messages', [])
                        if not messages:
                            logging.debug(f"⊘ Skipping empty chat: {chat_name}")
                            continue
                        
                        logging.info(f"📝 Processing: {chat_name} ({len(messages)} messages)")
                        total_chats += 1
                        
                        # Group messages by date
                        files: Dict[str, List[str]] = {}
                        
                        for msg in messages:
                            try:
                                md, date = self.process_message(msg, chat_folder, chat_name)
                                if md:
                                    files.setdefault(date, []).append(md)
                                    total_messages += 1
                            except Exception as e:
                                logging.warning(f"Failed to process message in {chat_name}: {e}")
                                continue
                        
                        # Write date-based files
                        for date, msgs in files.items():
                            out_file = chat_folder / f"{date}.md"
                            try:
                                with open(out_file, 'w', encoding='utf-8') as out:
                                    out.write("---\ntype: chat\ntags: [telegram/import]\n---\n\n")
                                    out.write('\n\n'.join(msgs))
                            except Exception as e:
                                logging.error(f"Failed to write {out_file}: {e}")
                    
                    except Exception as e:
                        logging.error(f"Failed to process chat: {e}")
                        continue
            
            # Write index file
            try:
                with open(self.vault_root / "Index.md", 'w', encoding='utf-8') as idx:
                    idx.write('\n'.join(index_lines))
            except Exception as e:
                logging.error(f"Failed to write index: {e}")
            
            # Write search index (JSONL)
            try:
                with open(self.vault_root / "search_index.jsonl", 'w', encoding='utf-8') as s:
                    for entry in self.search_index:
                        s.write(json.dumps(entry, ensure_ascii=False) + '\n')
            except Exception as e:
                logging.error(f"Failed to write search index: {e}")
            
            # Write search index sample (JSON)
            try:
                with open(self.vault_root / "search_index_sample.json", 'w', encoding='utf-8') as s:
                    json.dump(
                        self.search_index[:MAX_SEARCH_INDEX_SAMPLE],
                        s,
                        ensure_ascii=False,
                        indent=2
                    )
            except Exception as e:
                logging.error(f"Failed to write search index sample: {e}")
            
            # Final statistics
            logging.info(f"✅ Conversion complete!")
            logging.info(f"📊 Statistics:")
            logging.info(f"   - Chats: {total_chats}")
            logging.info(f"   - Messages: {total_messages}")
            logging.info(f"   - Search entries: {len(self.search_index)}")
            logging.info(f"   - Media files indexed: {len(self.media_index)}")
        
        except Exception as e:
            logging.error(f"Fatal error during conversion: {e}")
            raise


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Telegram Export to Obsidian Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python telegram_converter.py -i ./telegram_export -o ./obsidian_vault
  python telegram_converter.py -i ./telegram_export -o ./obsidian_vault -v
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to Telegram export folder (must contain result.json)'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Path to Obsidian vault (will be created if not exists)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--log-file',
        help='Write logs to file'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logger(args.verbose, args.log_file)
    
    try:
        # Validate input
        input_path = Path(args.input)
        if not input_path.exists():
            logging.error(f"❌ Input path does not exist: {input_path}")
            return 1
        
        if not (input_path / 'result.json').exists():
            logging.error(f"❌ result.json not found in {input_path}")
            logging.error("   Make sure you exported your Telegram data correctly")
            return 1
        
        # Run converter
        converter = TelegramObsidianConverter(str(input_path), args.output)
        converter.run()
        
        return 0
    
    except KeyboardInterrupt:
        logging.info("⚠️  Interrupted by user")
        return 130
    except FileNotFoundError as e:
        logging.error(f"❌ {e}")
        return 1
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
