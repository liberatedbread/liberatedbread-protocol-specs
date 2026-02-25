# Documentation Guide

## Using the Device Template

Copy `docs/devices/_template.md` and fill in each section.

### Tips

- Be specific about byte offsets and lengths
- Use hex notation: `0x01`, `0xFF`
- Include both request and response formats
- Document error responses too
- Screenshots of nRF Connect are very helpful

## Building Docs Locally

```bash
pip install -r requirements.txt
mkdocs serve
```

Preview at http://localhost:8000
