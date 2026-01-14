# Gemini API Summary Generation Failure - Analysis

## Current Status
✅ **Clustering works** - Articles are being fetched and clustered successfully  
❌ **Summary generation fails** - Returns "Failed to generate summary" error  
⚠️ **Error not logged** - Exception caught but actual error message not visible in logs  

## Hypothesis: What's Failing (Assuming API Key is Correct)

### 1. **Model Name Issue** (MOST LIKELY)
**Problem:** Code uses `"gemini-2.0-flash"` which likely doesn't exist.

**Evidence:**
- All files consistently use `gemini-2.0-flash`
- This model name is not standard Gemini naming convention
- Standard models are: `gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-pro`

**Fix:** Change to `"gemini-1.5-flash"` or `"gemini-1.5-pro"`

```python
# Current (likely wrong):
model = genai.GenerativeModel("gemini-2.0-flash")

# Should be:
model = genai.GenerativeModel("gemini-1.5-flash")  # Fast, cheaper
# OR
model = genai.GenerativeModel("gemini-1.5-pro")    # More capable
```

---

### 2. **Deprecated Package Issue** (LIKELY)
**Problem:** Using deprecated `google.generativeai` package.

**Evidence from logs:**
```
FutureWarning: All support for the `google.generativeai` package has ended.
It will no longer be receiving updates or bug fixes. 
Please switch to the `google.genai` package as soon as possible.
```

**Impact:**
- Package may have breaking changes
- Response format might have changed
- Some features might not work

**Fix:** Migrate to `google.genai` package (but this is a larger refactor)

---

### 3. **Response Format Change** (POSSIBLE)
**Problem:** Gemini API response structure may have changed.

**Current code expects:**
```python
response = model.generate_content(base_prompt)
return response.text  # Assumes .text attribute exists
```

**Possible issues:**
- Response might be blocked by safety filters (no text, only finish_reason)
- Response might use different attribute name
- Response might need error handling for blocked content

**Fix:** Add proper error handling:
```python
response = model.generate_content(base_prompt)

# Check if response was blocked
if response.candidates and len(response.candidates) > 0:
    candidate = response.candidates[0]
    if candidate.finish_reason == 'SAFETY':
        raise ValueError("Response blocked by content safety filters")
    if candidate.finish_reason == 'RECITATION':
        raise ValueError("Response blocked due to recitation")
    
    # Get text from parts
    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
        return candidate.content.parts[0].text
    elif hasattr(candidate, 'text'):
        return candidate.text

if hasattr(response, 'text'):
    return response.text

raise ValueError("Unexpected response format")
```

---

### 4. **Prompt Too Long** (POSSIBLE)
**Problem:** The prompt includes ALL cluster summaries, which could be very long.

**Evidence:**
- Logs show 590 articles collected for "World News"
- Multiple clusters created (19 clusters)
- Each cluster has summaries
- All concatenated into one prompt

**Impact:**
- May exceed token limits
- May cause timeout
- May cause API errors

**Fix:** 
- Truncate cluster summaries if total length exceeds limit
- Process in batches
- Use streaming API

---

### 5. **Content Safety Filters** (POSSIBLE)
**Problem:** News content might trigger Gemini's safety filters.

**Evidence:**
- News articles contain topics like violence, politics, conflicts
- Some articles mention "Iran", "protests", "executions", etc.
- Gemini has strict content safety policies

**Impact:**
- Response might be blocked entirely
- No error thrown, just empty/blocked response

**Fix:**
- Check `finish_reason` in response
- Handle safety blocks gracefully
- Adjust safety settings if possible

---

### 6. **JSON Parsing Failure** (POSSIBLE)
**Problem:** Gemini returns valid text, but JSON parsing fails.

**Current flow:**
1. `get_final_summary()` returns `response.text`
2. `extract_braces_content()` extracts JSON from text
3. `json.loads()` parses JSON

**Possible issues:**
- Gemini wraps JSON in markdown code fences (```json ... ```)
- Gemini includes extra text before/after JSON
- JSON has syntax errors (trailing commas, single quotes, etc.)

**Fix:** Improve JSON extraction and parsing with better error handling

---

## Recommended Fix Priority

### **IMMEDIATE (Do First):**
1. **Change model name** from `gemini-2.0-flash` to `gemini-1.5-flash`
2. **Add response validation** - check `finish_reason` and handle safety blocks
3. **Improve error logging** - log the actual exception (already done)

### **SHORT TERM:**
4. **Add prompt length check** - truncate if too long
5. **Improve JSON parsing** - handle markdown code fences

### **LONG TERM:**
6. **Migrate to `google.genai`** package (larger refactor)

---

## Testing Strategy

After fixing, test with:
1. Small topic (few articles) - verify basic functionality
2. Large topic (many articles) - verify prompt length handling
3. Sensitive content - verify safety filter handling
4. Check logs for actual error messages

---

## Files That Need Updates

All files using Gemini API:
- `_1nbox_ai/news.py` - Summary generation (main issue)
- `_1nbox_ai/answer.py` - Q&A generation
- `_1nbox_ai/chat_views.py` - Chat responses
- `_1nbox_ai/genie_views.py` - Genie analysis
- `_1nbox_ai/bites_views.py` - Bites digests

