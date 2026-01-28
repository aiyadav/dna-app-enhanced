# Keyword & Relevance Logging Documentation

## Overview
The system provides comprehensive logging showing how keywords are used and how relevance scores are calculated.

## Log Location
- **File**: `/home/ec2-user/dna-app-enhanced/nohup.out` (on EC2)
- **Local**: Console output when running `python app.py`

## What Gets Logged

### 1. Article Information
```
================================================================================
KEYWORD & RELEVANCE ANALYSIS LOG
================================================================================
Article Title: [Article Title]
Article URL: [Article URL]
Content Length: [X] characters (using first 2500 for analysis)
Available Categories: [List of categories]
```

### 2. Keywords Being Used
```
Active Topics Count: [N]

KEYWORDS BEING USED FOR RELEVANCE:
  Topic: 'Technology'
    Keywords: AI, machine learning, software, tech, digital
  Topic: 'Finance'
    Keywords: banking, federal reserve, interest rates, monetary policy
  Topic: 'Economics'
    Keywords: GDP, unemployment, economic growth, recession, market
```

### 3. Relevance Calculation Method
```
RELEVANCE CALCULATION METHOD:
  - Type: AI-driven contextual analysis (NOT simple keyword matching)
  - Model: AWS Bedrock Claude 3 Haiku
  - Process: AI performs semantic analysis of article content against topic keywords
  - Scoring: AI assigns 0-100 score based on contextual relevance
```

### 4. Prompt Context
```
PROMPT CONTEXT SENT TO AI:
  Prompt length: [X] characters
  Article content included: [X] characters
  Topics/Keywords included: Yes/No
```

### 5. AI Response
```
AI RESPONSE RECEIVED:
  Raw response: {"bullets": [...], "category": "...", "relevancy_score": 85, "author": "..."}
```

### 6. Relevance Results
```
RELEVANCE CALCULATION RESULTS:
  Assigned Category: 'Technology'
  Relevancy Score: 85/100
  Extracted Author: 'John Doe'
  Summary Bullets: 4 items

SCORING CONTEXT:
  - Score is AI-determined based on semantic understanding
  - AI considers: topic keywords, article content, context, and meaning
  - NOT based on simple keyword frequency or exact matching
================================================================================
```

## Key Points

### Relevance is NOT Based Solely on Keywords
The system uses **AI-driven contextual analysis**, not simple keyword matching:

1. **Keywords as Guidance**: Topic keywords are provided to the AI as context
2. **Semantic Understanding**: AI analyzes the meaning and context of the article
3. **Contextual Factors Considered**:
   - Article content and meaning
   - Topic keywords and their context
   - Semantic relationships between concepts
   - Overall relevance to the topic domain
   - Writing style and intent

### Relevance Calculation Steps

1. **Input Preparation**
   - Article title, content, and metadata collected
   - Active topics and their keywords retrieved
   - Categories list prepared

2. **Prompt Construction**
   - Article content (first 2500 chars) included
   - All topic keywords embedded in prompt
   - Relevancy criteria explained to AI

3. **AI Analysis**
   - AWS Bedrock Claude 3 Haiku processes the prompt
   - AI performs semantic analysis
   - Considers keywords in context, not just frequency

4. **Score Assignment**
   - AI returns relevancy score (0-100)
   - Score reflects contextual relevance, not keyword count
   - Threshold filtering applied (default: 60)

5. **Result Logging**
   - All steps logged with details
   - Score and reasoning context recorded

## How to View Logs

### On EC2:
```bash
# View recent logs
tail -100 /home/ec2-user/dna-app-enhanced/nohup.out

# Follow logs in real-time
tail -f /home/ec2-user/dna-app-enhanced/nohup.out

# Search for keyword logs
grep -A 50 "KEYWORD & RELEVANCE" /home/ec2-user/dna-app-enhanced/nohup.out
```

### Locally:
```bash
# Run the app and watch console output
python app.py

# Logs will appear in console when processing articles
```

## Example Log Output

```
INFO:services:================================================================================
INFO:services:KEYWORD & RELEVANCE ANALYSIS LOG
INFO:services:================================================================================
INFO:services:Article Title: Federal Reserve Announces New Interest Rate Policy
INFO:services:Article URL: https://example.com/article
INFO:services:Content Length: 1850 characters (using first 2500 for analysis)
INFO:services:Available Categories: ['Technology', 'Finance', 'Economics']

INFO:services:Active Topics Count: 3

INFO:services:KEYWORDS BEING USED FOR RELEVANCE:
INFO:services:  Topic: 'Technology'
INFO:services:    Keywords: AI, machine learning, software, tech, digital
INFO:services:  Topic: 'Finance'
INFO:services:    Keywords: banking, federal reserve, interest rates, monetary policy, inflation
INFO:services:  Topic: 'Economics'
INFO:services:    Keywords: GDP, unemployment, economic growth, recession, market

INFO:services:RELEVANCE CALCULATION METHOD:
INFO:services:  - Type: AI-driven contextual analysis (NOT simple keyword matching)
INFO:services:  - Model: AWS Bedrock Claude 3 Haiku
INFO:services:  - Process: AI performs semantic analysis of article content against topic keywords
INFO:services:  - Scoring: AI assigns 0-100 score based on contextual relevance

INFO:services:PROMPT CONTEXT SENT TO AI:
INFO:services:  Prompt length: 2847 characters
INFO:services:  Article content included: 1850 characters
INFO:services:  Topics/Keywords included: Yes

INFO:services:Sending request to AWS Bedrock...

INFO:services:AI RESPONSE RECEIVED:
INFO:services:  Raw response: {"bullets": ["Federal Reserve maintains current interest rate at 5.25%", "Policy decision reflects ongoing inflation concerns", "Economic indicators show mixed signals"], "category": "Finance", "relevancy_score": 92, "author": "Jane Smith"}

INFO:services:RELEVANCE CALCULATION RESULTS:
INFO:services:  Assigned Category: 'Finance'
INFO:services:  Relevancy Score: 92/100
INFO:services:  Extracted Author: 'Jane Smith'
INFO:services:  Summary Bullets: 3 items

INFO:services:SCORING CONTEXT:
INFO:services:  - Score is AI-determined based on semantic understanding
INFO:services:  - AI considers: topic keywords, article content, context, and meaning
INFO:services:  - NOT based on simple keyword frequency or exact matching
INFO:services:================================================================================
```

## Triggering Logs

To see these logs in action:

1. Go to the dashboard: http://44.205.255.62:5000
2. Click "Refresh News" button
3. Wait for processing to complete
4. Check logs using the commands above

The logs will show detailed information for each article processed, including all keywords used and how relevance was calculated.
