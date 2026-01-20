# Briefed Genie - Two-Stage Analysis Workflow

## Overview

Genie now uses a two-stage workflow to generate more accurate, context-rich strategic intelligence:

1. **Stage 1: Questionnaire Generation** - Clarify the user's intent with targeted questions
2. **Stage 2: Deep Analysis** - Generate comprehensive analysis using answers, organization context, and selected news topics

---

## Complete User Flow

### Step 1: User Enters Query
- User types a complex strategic question in the input field
- Example: "What is the likelihood that the AI bubble bursts in the next three months?"
- User clicks "Generate Insight"

### Step 2: Questionnaire Generation
**Frontend:**
- Button shows "Generating..."
- Loading screen appears with message: "Generating questionnaire..."

**Backend (`POST /genie/questionnaire/`):**
- Receives the query
- Uses Gemini 2.5 Flash Lite to generate 3-5 clarifying questions
- Questions can be:
  - **Multiple choice** with 4-6 options (last option is always "Other" for text input)
  - **Text input** for open-ended responses

**Response Format:**
```json
{
  "success": true,
  "questionnaire": {
    "questions": [
      {
        "id": 1,
        "question": "What is your primary timeframe for this decision?",
        "type": "multiple_choice",
        "options": ["1-3 months", "3-6 months", "6-12 months", "1+ years", "Other"]
      },
      {
        "id": 2,
        "question": "Which stakeholders are most impacted?",
        "type": "multiple_choice",
        "options": ["Customers", "Investors", "Employees", "Partners", "Other"]
      },
      {
        "id": 3,
        "question": "Any additional context or constraints?",
        "type": "text",
        "options": []
      }
    ]
  }
}
```

### Step 3: Display Questionnaire
**Frontend:**
- Replaces the input section with an interactive questionnaire form
- Renders each question:
  - Multiple choice: Radio buttons with hover effects
  - "Other" option: Shows text input when selected
  - Text questions: Textarea for detailed responses
- Shows **topic selector** with checkboxes for all user's topics (all checked by default)
- "Generate Analysis" button at bottom

### Step 4: User Completes Questionnaire
- User answers 3-5 questions
- User selects which topics to include for news context (can select multiple)
- User clicks "Generate Analysis"

### Step 5: Final Analysis Generation
**Frontend:**
- Hides questionnaire
- Shows loading with message: "Analyzing sources and generating insights..."

**Backend (`POST /genie/analyze/`):**

**Request:**
```json
{
  "query": "Original user query",
  "questionnaire_answers": [
    {
      "question": "What is your primary timeframe?",
      "answer": "3-6 months"
    },
    {
      "question": "Which stakeholders are most impacted?",
      "answer": "Investors"
    }
  ],
  "topic_ids": [1, 3, 5]
}
```

**Processing:**
1. Authenticates user via Firebase token
2. Loads organization profile with:
   - Name, industry, description, headquarters
   - Employee count, annual revenue
   - Key products, competitors, target markets
   - Strategic priorities
3. Fetches news context from selected topics:
   - Latest summaries (final_summary)
   - Top 3 cluster summaries per topic
   - Max 15,000 characters total
4. Builds comprehensive prompt with:
   - Organization context
   - Questionnaire Q&A
   - News context
   - User's original query
5. Calls Gemini 2.5 Flash Lite for analysis
6. Saves to `GenieAnalysis` database

**Response Format:**
```json
{
  "id": 123,
  "status": "completed",
  "query": "Original query",
  "results": {
    "top_insight": {
      "title": "Main finding in one sentence",
      "summary": "2-3 sentence explanation",
      "relevance_badge": "High Relevance"
    },
    "key_takeaways": [
      "Takeaway 1",
      "Takeaway 2",
      "Takeaway 3",
      "Takeaway 4",
      "Takeaway 5"
    ],
    "featured_quote": {
      "text": "Insightful quote",
      "attribution": "Source name and title"
    },
    "sources_analyzed": 8,
    "full_analysis": {
      "executive_summary": "...",
      "current_dynamics": "...",
      "positive_indicators": ["..."],
      "negative_indicators": ["..."],
      "neutral_factors": ["..."],
      "historical_context": "...",
      "risk_assessment": [
        {
          "category": "Market Risk",
          "description": "...",
          "severity": "medium"
        }
      ],
      "probability_assessment": {
        "scenario_1": {"name": "Optimistic", "probability": "30-40%"},
        "scenario_2": {"name": "Base case", "probability": "40-50%"},
        "scenario_3": {"name": "Pessimistic", "probability": "15-25%"}
      }
    },
    "recommendations": {
      "strategic_planning": "...",
      "risk_management": "...",
      "timing": "..."
    },
    "further_questions": [
      "Question 1",
      "Question 2",
      "Question 3",
      "Question 4"
    ],
    "confidence_score": 0.85,
    "data_freshness": "2024-01-20"
  },
  "created_at": "...",
  "completed_at": "..."
}
```

### Step 6: Display Results
**Frontend:**
- Hides loading
- Shows results section with beautifully formatted analysis:
  - **Top Insight Card** - Main finding with relevance badge
  - **Key Takeaways** - Bullet list of 5 main points
  - **Featured Quote** - Highlighted quote with attribution
  - **Sources Count** - Number of sources analyzed
  - **Full Analysis** - Detailed markdown-formatted analysis including:
    - Executive summary
    - Current dynamics
    - Positive/negative/neutral indicators
    - Historical context
    - Risk assessment
    - Probability scenarios
  - **Recommendations** - Actionable steps for:
    - Strategic planning
    - Risk management
    - Timing considerations
  - **Further Questions** - Follow-up questions to explore

---

## API Endpoints

### 1. Generate Questionnaire
```
POST /genie/questionnaire/
Headers: Authorization: Bearer <firebase_token>
Body: { "query": "user question" }
Response: { "success": true, "questionnaire": {...} }
```

### 2. Generate Analysis
```
POST /genie/analyze/
Headers: Authorization: Bearer <firebase_token>
Body: {
  "query": "user question",
  "questionnaire_answers": [{question, answer}, ...],
  "topic_ids": [1, 2, 3]
}
Response: { "id": 123, "status": "completed", "results": {...} }
```

### 3. Other Endpoints (unchanged)
- `GET /genie/organization/` - Get org profile
- `PUT /genie/organization/` - Update org profile (admin only)
- `GET /genie/analyses/` - List past analyses
- `GET /genie/analyses/<id>/` - Get specific analysis
- `DELETE /genie/analyses/<id>/delete/` - Delete analysis

---

## Key Features

### ✅ Dynamic Questionnaire
- AI-generated questions tailored to user's query
- Mix of multiple choice and text inputs
- "Other" option for custom responses
- Smooth UI with hover effects

### ✅ Topic Selection
- Users choose which topics provide news context
- All topics selected by default
- Helps narrow focus for more relevant analysis

### ✅ Organization Context
- Automatically includes org profile in analysis
- Personalized insights based on:
  - Industry, products, competitors
  - Strategic priorities
  - Target markets

### ✅ Rich Analysis Output
- Structured JSON matching the demo UI
- Multiple analysis perspectives
- Probability assessments
- Actionable recommendations
- Follow-up questions

### ✅ Beautiful UI
- Smooth transitions between stages
- Loading states with descriptive messages
- Professional questionnaire design
- Results display matches demo layout

---

## Files Modified

### Backend
- `1nbox/_1nbox_ai/genie_views.py` - Added questionnaire generation, updated analysis flow
- `1nbox/_1nbox_ai/urls.py` - Added `/genie/questionnaire/` endpoint

### Frontend
- `1nbox-frontend/js/genie.js` - Complete workflow implementation
- `1nbox-frontend/css/genie.css` - Questionnaire styling
- `1nbox-frontend/pages/genie.html` - Added Firebase/API config scripts

---

## Next Steps

To test the new workflow:

1. **Start the backend**:
   ```bash
   cd 1nbox
   python manage.py runserver
   ```

2. **Open the frontend**:
   ```
   Open: 1nbox-frontend/pages/genie.html
   ```

3. **Test flow**:
   - Log in with Firebase
   - Enter a complex strategic question
   - Answer the generated questionnaire
   - Select relevant topics
   - Review the comprehensive analysis

---

## Benefits of Two-Stage Approach

1. **Better Context** - Questions clarify user intent, timeframes, priorities
2. **Targeted Analysis** - AI has more information to work with
3. **User Engagement** - Interactive experience keeps users involved
4. **Flexibility** - Users control which topics contribute to analysis
5. **Accuracy** - More targeted prompts = better quality outputs
6. **Transparency** - Users see exactly what context is being used

