# Genie Testing Guide

## Quick Start

### 1. Start the Backend
```bash
cd 1nbox
python manage.py runserver
```

### 2. Open Frontend
Open in browser: `1nbox-frontend/pages/genie.html`

---

## Test Scenarios

### Scenario 1: Basic Workflow
**Goal:** Test the complete two-stage flow

1. **Login** with Firebase credentials
2. **Enter query:** "What is the likelihood that the AI bubble bursts in the next three months?"
3. **Click** "Generate Insight"
4. **Verify:**
   - Loading screen appears with "Generating questionnaire..."
   - Questionnaire loads with 3-5 questions
   - Topics are listed with checkboxes (all checked)
5. **Answer questions:**
   - Select timeframe: "3-6 months"
   - Select stakeholders: "Investors"
   - Add text context (optional)
6. **Select topics:** Keep all checked or uncheck some
7. **Click** "Generate Analysis"
8. **Verify:**
   - Loading screen shows "Analyzing sources and generating insights..."
   - Results appear with all sections populated:
     - Top Insight
     - Key Takeaways (5 items)
     - Featured Quote
     - Sources count
     - Full Analysis (detailed sections)
     - Recommendations
     - Further Questions

### Scenario 2: Multiple Choice with "Other"
**Goal:** Test "Other" text input functionality

1. Generate questionnaire
2. Select "Other" for a multiple choice question
3. **Verify:** Text input appears below
4. Enter custom text
5. Submit and check that custom text is included in analysis context

### Scenario 3: Topic Selection
**Goal:** Test filtering news by topics

1. Generate questionnaire
2. **Uncheck all topics** except one
3. Submit questionnaire
4. **Verify:** Analysis only references news from that single topic

### Scenario 4: Different Query Types
**Goal:** Test various strategic questions

Try these queries:
- "How will new EU regulations affect our AI product roadmap?"
- "Should we invest in quantum computing technology?"
- "What are the risks of expanding into Asian markets?"
- "How can we compete with [Competitor Name] in [Market]?"

**Verify:** Questionnaire questions are relevant to each query type

### Scenario 5: Error Handling
**Goal:** Test error states

1. **Test empty query:**
   - Leave input blank and click "Generate Insight"
   - **Verify:** Input border turns red, error persists for 2 seconds
   
2. **Test network failure:**
   - Disconnect network
   - Submit query
   - **Verify:** User-friendly error message appears

3. **Test backend failure:**
   - Stop backend server
   - Submit query
   - **Verify:** Error is caught and displayed

---

## Expected API Calls

### Call 1: Questionnaire Generation
```
POST https://briefed-production.up.railway.app/genie/questionnaire/
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "User's question"
}
```

**Expected Response:**
```json
{
  "success": true,
  "questionnaire": {
    "questions": [...]
  }
}
```

### Call 2: Get User Topics
```
GET https://briefed-production.up.railway.app/get_user_organization_data/
Authorization: Bearer <token>
```

**Expected Response:**
```json
{
  "topics": [
    {"id": 1, "name": "AI & Technology"},
    {"id": 2, "name": "Financial Markets"}
  ],
  ...
}
```

### Call 3: Final Analysis
```
POST https://briefed-production.up.railway.app/genie/analyze/
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "User's question",
  "questionnaire_answers": [
    {"question": "Q1", "answer": "A1"},
    {"question": "Q2", "answer": "A2"}
  ],
  "topic_ids": [1, 2, 3]
}
```

**Expected Response:**
```json
{
  "id": 123,
  "status": "completed",
  "results": {
    "top_insight": {...},
    "key_takeaways": [...],
    "full_analysis": {...},
    ...
  }
}
```

---

## Debugging Checklist

### Frontend Issues

**Questionnaire not appearing:**
- [ ] Check browser console for errors
- [ ] Verify Firebase authentication is working
- [ ] Check network tab for failed API calls
- [ ] Verify API_BASE_URL is set correctly

**Topics not loading:**
- [ ] Check if user has topics in database
- [ ] Verify `/get_user_organization_data/` returns topics
- [ ] Check console for errors in `loadUserTopics()`

**Results not displaying:**
- [ ] Check that `results` object has expected structure
- [ ] Verify all required fields exist in response
- [ ] Check console for JavaScript errors in `displayResults()`

### Backend Issues

**Questionnaire generation fails:**
- [ ] Verify GEMINI_API_KEY is set in environment
- [ ] Check Django console for errors
- [ ] Test Gemini API directly
- [ ] Verify user exists in database

**Analysis generation fails:**
- [ ] Check if organization has topics
- [ ] Verify topics have summaries
- [ ] Check GEMINI_API_KEY
- [ ] Look for JSON parsing errors in logs

**News context is empty:**
- [ ] Verify selected topics have summaries
- [ ] Check `topic.summaries.first()` returns data
- [ ] Verify summary structure (final_summary, cluster_summaries)

---

## Browser Console Commands for Testing

### Check if Firebase is loaded:
```javascript
console.log(firebase.auth().currentUser);
```

### Check if API base URL is set:
```javascript
console.log(window.API_BASE_URL);
```

### Manually test questionnaire endpoint:
```javascript
const user = firebase.auth().currentUser;
user.getIdToken().then(token => {
  fetch(`${API_BASE_URL}/genie/questionnaire/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query: 'Test query' })
  })
  .then(r => r.json())
  .then(data => console.log(data));
});
```

### Manually test analysis endpoint:
```javascript
const user = firebase.auth().currentUser;
user.getIdToken().then(token => {
  fetch(`${API_BASE_URL}/genie/analyze/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query: 'Test query',
      questionnaire_answers: [
        { question: 'Q1', answer: 'A1' }
      ],
      topic_ids: [1]
    })
  })
  .then(r => r.json())
  .then(data => console.log(data));
});
```

---

## Performance Expectations

| Stage | Expected Time | What's Happening |
|-------|---------------|------------------|
| Questionnaire Generation | 2-5 seconds | Gemini API call to generate 3-5 questions |
| Final Analysis | 5-15 seconds | News context gathering + Gemini API call for full analysis |

**Note:** Times may vary based on:
- Gemini API response time
- Number of topics selected
- Amount of news context (up to 15K chars)
- Complexity of query

---

## Common Issues & Solutions

### Issue: "User not found" error
**Solution:** 
- Ensure user is logged in with Firebase
- Verify user exists in Django database
- Check email matches between Firebase and Django

### Issue: Empty news context
**Solution:**
- Verify organization has topics
- Check that topics have summaries
- Run summary generation if needed

### Issue: Questionnaire has only fallback questions
**Solution:**
- Check Gemini API key is valid
- Verify API quota isn't exceeded
- Check Django logs for specific error

### Issue: Analysis returns fallback structure
**Solution:**
- Gemini returned non-JSON response
- Check prompt structure in `generate_analysis()`
- May need to adjust JSON extraction logic

### Issue: "Other" input not showing
**Solution:**
- Check that radio button event listeners are attached
- Verify `renderQuestion()` includes "Other" option
- Check CSS for `.other-input` display properties

---

## Success Criteria

✅ **Workflow completes end-to-end**
- Query → Questionnaire → Analysis → Results

✅ **UI is responsive and smooth**
- Loading states appear correctly
- Transitions are smooth
- No layout shifts

✅ **Questionnaire is dynamic**
- Questions change based on query
- "Other" inputs work correctly
- Form validation works

✅ **Analysis is comprehensive**
- All sections populated
- Data is relevant to query
- Organization context evident

✅ **Error handling works**
- Empty query validation
- Network errors caught
- User-friendly messages

---

## Next Steps After Testing

1. **Gather user feedback** on questionnaire quality
2. **Tune prompts** based on analysis quality
3. **Add analytics** to track:
   - Question response patterns
   - Most selected topics
   - Analysis completion rate
4. **Optimize performance:**
   - Consider caching news context
   - Add loading progress indicators
   - Implement pagination for long analyses
5. **Enhance UI:**
   - Add animations
   - Improve mobile responsiveness
   - Add export/share features

