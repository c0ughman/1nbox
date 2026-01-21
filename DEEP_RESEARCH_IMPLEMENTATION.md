# Deep Research Implementation for Genie

## Overview

This implementation integrates **Gemini Deep Research** into the Briefed Genie product. Deep Research runs in the background while users complete the questionnaire, providing comprehensive web-based research to enhance the final analysis.

---

## Key Features

✅ **Research Type Toggle**: Users can choose between Quick, Comprehensive, or Deep Research  
✅ **Parallel Execution**: Deep Research starts immediately when user clicks "Generate" and runs while questionnaire is being answered  
✅ **Smart Waiting**: Loading screen waits for Deep Research to complete before generating final report  
✅ **Enriched Analysis**: Final report includes organization context + questionnaire + news + **Deep Research findings**  
✅ **Error Handling**: Clear error messages during development, graceful handling in production  

---

## User Flow

```
1. User enters query
   ↓
2. User selects research type: Quick / Comprehensive / Deep Research
   ↓
3. User clicks "Generate Insight"
   ↓
4. Backend starts two parallel processes:
   ├─ Generate questionnaire (3-5 seconds)
   └─ Start Deep Research if "Deep" selected (runs in background)
   ↓
5. User answers questionnaire (1-3 minutes)
   ↓
6. User clicks "Generate Analysis"
   ↓
7. Loading screen: "Conducting deep research..."
   ↓
8. Backend polls for Deep Research completion (3-15 minutes)
   ↓
9. Generate final report with all context:
   - Organization profile
   - Questionnaire answers
   - News from selected topics
   - Deep Research findings ✨
   ↓
10. Display comprehensive analysis
```

---

## Technical Implementation

### Database Changes

**Model**: `GenieAnalysis` (`1nbox/_1nbox_ai/models.py`)

Added fields:
- `research_type` - CharField: 'quick', 'comprehensive', or 'deep'
- `deep_research_id` - CharField: Stores Gemini Interactions API ID
- `deep_research_results` - TextField: Stores the research findings

**Migration**: `0007_add_deep_research_fields.py`

### Backend Changes

**File**: `1nbox/_1nbox_ai/genie_views.py`

#### 1. New Helper Functions

**`start_deep_research(query, organization)`**
- Starts Deep Research using Gemini Interactions API
- Uses agent: `deep-research-pro-preview-12-2025`
- Background execution: `background=True`
- Returns: interaction ID for tracking
- Prompt includes:
  - User's query
  - Organization context
  - Decision-making focus
  - Custom instructions for actionable insights

**`get_deep_research_results(interaction_id, timeout_minutes=15)`**
- Polls for Deep Research completion
- Polls every 10 seconds
- Default timeout: 15 minutes (can take up to 60 minutes per Gemini docs)
- Returns: Research findings text
- Raises: TimeoutError or Exception on failure

#### 2. Updated Endpoints

**`POST /genie/questionnaire/`**

New parameters:
- `research_type` (required): 'quick', 'comprehensive', or 'deep'

New behavior:
- If `research_type == 'deep'`: Starts Deep Research immediately
- Returns `deep_research_id` in response if Deep Research was started

Request:
```json
{
  "query": "What is the likelihood that the AI bubble bursts?",
  "research_type": "deep"
}
```

Response:
```json
{
  "success": true,
  "questionnaire": { ... },
  "research_type": "deep",
  "deep_research_id": "interactions/abc123xyz"
}
```

**`POST /genie/analyze/`**

New parameters:
- `research_type` (required): 'quick', 'comprehensive', or 'deep'
- `deep_research_id` (optional): ID from questionnaire response

New behavior:
- If `research_type == 'deep'`: Waits for Deep Research to complete
- Passes deep research results to `generate_analysis()`
- Returns error if Deep Research fails (during development)

Request:
```json
{
  "query": "Original query",
  "questionnaire_answers": [...],
  "topic_ids": [1, 3, 5],
  "research_type": "deep",
  "deep_research_id": "interactions/abc123xyz"
}
```

Response:
```json
{
  "id": 123,
  "status": "completed",
  "query": "...",
  "results": { ... },
  "research_type": "deep",
  "deep_research_included": true,
  "created_at": "...",
  "completed_at": "..."
}
```

#### 3. Enhanced Analysis Generation

**`generate_analysis(..., deep_research_results="")`**

- New parameter: `deep_research_results`
- If provided, adds "DEEP RESEARCH FINDINGS" section to prompt
- Truncates deep research to 25,000 characters to avoid token limits
- Final prompt includes all context for comprehensive decision support

### Frontend Changes

**File**: `1nbox-frontend/js/genie.js`

#### New State Variables

```javascript
let currentResearchType = 'comprehensive';  // Track selected research type
let deepResearchId = null;                  // Track Deep Research interaction ID
```

#### Updated Dropdown Handler

Maps UI selections to API values:
- "Quick" → `quick`
- "Comprehensive" → `comprehensive`
- "Deep Research" → `deep`

#### Updated `submitQuery()`

- Sends `research_type` to questionnaire endpoint
- Stores `deep_research_id` from response
- Logs Deep Research start to console

#### Updated `handleQuestionnaireSubmit()`

- Sends `research_type` and `deep_research_id` to analyze endpoint
- Shows "Conducting deep research..." for deep research requests
- Includes both fields in request body

---

## Deep Research Prompt Design

The Deep Research prompt is specifically crafted for **decision-making support**:

### Prompt Structure

1. **Decision Context**: User's query framed as a decision
2. **Organization Background**: Industry, products, competitors, strategic priorities
3. **Research Objectives**: What information is needed
4. **Investigation Areas**:
   - Current market dynamics & trends
   - Historical context & precedents
   - Risk analysis
   - Opportunity assessment
   - Expert perspectives & analysis
   - Quantitative data & metrics
   - Stakeholder considerations
5. **Instructions**: 
   - Focus on actionable insights
   - Prioritize recent information (6-12 months)
   - Include specific data points and citations
   - Consider multiple scenarios
   - Be thorough and objective

### Example Prompt

```
You are conducting comprehensive deep research to support a critical business decision.

DECISION CONTEXT:
Should we invest in AI infrastructure over the next 6 months?

ORGANIZATION BACKGROUND:
- Organization: TechCorp Inc.
- Industry: Enterprise Software
- Key Products: CRM Platform, Analytics Suite
- Main Competitors: Salesforce, HubSpot
...

RESEARCH OBJECTIVES:
Your goal is to gather ALL information necessary for making the best possible decision...

[Detailed investigation areas with specific instructions]
```

---

## Cost & Performance

### Expected Costs (per Deep Research task)

Based on Gemini Deep Research pricing:
- **Standard query**: $2-3 per task
- **Complex query**: $3-5 per task

Cost breakdown:
- ~80-160 search queries
- ~250k-900k input tokens (50-70% cached)
- ~60k-80k output tokens

### Expected Timing

- **Questionnaire generation**: 2-3 seconds
- **User questionnaire completion**: 1-3 minutes
- **Deep Research execution**: 3-15 minutes (can take up to 60 minutes max)
- **Final analysis generation**: 5-10 seconds

**Total user wait after questionnaire**: ~1-10 minutes depending on research complexity

### Cost Optimization

Only runs Deep Research when:
1. User explicitly selects "Deep Research" option
2. Query warrants comprehensive investigation

Uses cheaper models for other operations:
- Questionnaire: Gemini 3 Flash
- Final analysis: Gemini 3 Pro

---

## Error Handling

### Development Mode

**Errors are displayed to users** for debugging:

```json
{
  "error": "Deep Research failed: connection timeout"
}
```

### Timeout Handling

- Default timeout: 15 minutes
- Maximum timeout: 60 minutes (Gemini limit)
- If exceeded: Returns error in development
- Production: Could implement fallback to proceed without Deep Research

### Failure Scenarios

1. **Deep Research start fails**: Error returned immediately
2. **Deep Research times out**: Error after 15 minutes
3. **Deep Research API error**: Error with specific message
4. **Network interruption**: Polling continues until timeout

---

## Testing Instructions

### 1. Setup

Ensure environment variable is set:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 2. Run Migration

```bash
python manage.py migrate _1nbox_ai
```

### 3. Test Quick Research (No Deep Research)

1. Open Genie
2. Select "Quick" or "Comprehensive" from Analysis Depth dropdown
3. Enter query: "What are the latest trends in AI?"
4. Click "Generate Insight"
5. Complete questionnaire
6. Click "Generate Analysis"
7. **Expected**: Normal flow, no Deep Research

### 4. Test Deep Research

1. Open Genie
2. Select "Deep Research" from Analysis Depth dropdown
3. Enter query: "Should we invest in quantum computing in the next 12 months?"
4. Click "Generate Insight"
5. **Check browser console**: Should see "Deep Research started: interactions/..."
6. Complete questionnaire (Deep Research running in background)
7. Click "Generate Analysis"
8. **Expected**: Loading screen with "Conducting deep research..."
9. Wait 3-10 minutes
10. **Expected**: Comprehensive analysis with deep research findings

### 5. Monitor Backend Logs

Watch for:
```
Deep Research started: interactions/abc123xyz
Polling for Deep Research results: interactions/abc123xyz
Deep Research still processing... 540s remaining
Deep Research completed: interactions/abc123xyz
Deep Research completed successfully. Length: 15234 chars
```

### 6. Test Error Scenarios

**Scenario A: Invalid API Key**
- Temporarily unset GEMINI_API_KEY
- Try Deep Research
- Expected: Clear error message

**Scenario B: Network Issues**
- Simulate network interruption during polling
- Expected: Timeout error after 15 minutes

---

## API Model Names

### Current Models Used

| Component | Model | Purpose |
|-----------|-------|---------|
| Questionnaire | `gemini-3-flash-preview` | Fast, cheap question generation |
| Deep Research | `deep-research-pro-preview-12-2025` | Comprehensive web research |
| Final Analysis | `gemini-3-pro-preview` | Advanced reasoning for decision support |

**Note**: Deep Research is powered by Gemini 3 Pro (via the agent). The agent name is specified in the Interactions API, but the underlying model is Gemini 3 Pro.

---

## Production Considerations

### Before Going Live

1. **Test with production API keys** in staging environment
2. **Monitor costs** - Deep Research is expensive ($2-5 per request)
3. **Set rate limits** - Prevent abuse of expensive Deep Research
4. **Add usage tracking** - Log Deep Research usage per organization
5. **Consider user limits** - e.g., 5 deep research requests per month
6. **Implement retry logic** - Handle transient failures gracefully
7. **Add progress indicators** - Real-time updates during research (optional)

### Future Enhancements

- [ ] Streaming progress updates during Deep Research
- [ ] Ability to cancel Deep Research mid-execution
- [ ] Save and reuse Deep Research results for similar queries
- [ ] Add "Custom Instructions" field for user-specific research focus
- [ ] Usage analytics dashboard for organizations

---

## Troubleshooting

### Issue: Deep Research never completes

**Check**:
1. Backend logs for polling status
2. Network connectivity
3. Gemini API status

**Solution**: Increase timeout or check API limits

### Issue: "Failed to start Deep Research"

**Check**:
1. GEMINI_API_KEY is set correctly
2. API key has Interactions API access
3. Organization object has required fields

**Solution**: Verify API key and permissions

### Issue: Final analysis doesn't include Deep Research

**Check**:
1. `deep_research_included` flag in response
2. Backend logs for research completion
3. Database: Check `deep_research_results` field

**Solution**: Verify Deep Research actually completed before analysis

---

## Summary

This implementation provides a **production-ready Deep Research integration** for Genie with:

✅ Simple, reliable architecture  
✅ Parallel execution for better UX  
✅ Comprehensive error handling  
✅ Cost-effective design (only when requested)  
✅ Clear user feedback  
✅ Easy to test and debug  

The Deep Research feature transforms Genie from a quick analysis tool into a **comprehensive decision support system** backed by extensive web research, perfect for high-stakes strategic decisions.

