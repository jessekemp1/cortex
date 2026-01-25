# Kempion Research Site Improvement Plan
**Created:** 2026-01-20
**Context:** Site review critique identified credibility and engagement issues
**Goal:** Convert genuine interest into conversations without sacrificing research integrity

## Critical Insights from Review Analysis

### What the Reviewer Got Wrong
- **Chatbot-first UX**: Bad advice. Would destroy scannability and brand impact
- **Replace static content with chat**: Wrong. Different cognitive modes need different interfaces
- **SEO is mandatory**: Wrong frame. Selective discovery may be intentional for research partnerships

### What the Reviewer Got Right
- Chatbot is valuable but hidden
- Connection flow too lightweight (mailto insufficient)
- Broken UI element destroys credibility
- Performance should be measured (but not assumed problematic)

### Core Dysfunction (Five Whys)
**Problem:** Site doesn't convert genuine interest into conversations

1. Why don't interested visitors reach out? → Don't know what conversation you want or if they qualify
2. Why don't they know? → Site explains research framework, not collaboration model
3. Why framework over collaboration? → Content written to document work, not facilitate partnerships
4. Why document over facilitate? → Proud of research, want to explain fully
5. Why explain fully upfront? → **Using complexity as a filter for sophisticated visitors**

**Root cause:** Filtering for deep understanding may exclude time-constrained senior decision-makers who need faster value signal

---

## Tier 1: Fix Immediately (Credibility Destroyers)
**Timeline:** Today
**Effort:** 45 minutes total

### 1. Fix or Remove Broken EXPLORE Button
- **Current state:** Non-functional scroll indicator
- **Impact:** Destroys credibility for site about "precision and intelligence"
- **Decision:**
  - Option A: Implement functional scroll-to-content behavior
  - Option B: Remove entirely
- **Testing:** Mobile and desktop verification required

### 2. Add Meta Description and OpenGraph Tags
- **Current state:** Links share without preview/description
- **Impact:** Looks unfinished when shared professionally
- **Implementation:**
  - Meta description: ~155 characters summarizing research focus
  - OpenGraph tags: title, description, image for social sharing
  - Twitter Card tags for Twitter sharing

---

## Tier 2: High Impact, Low Effort (Week 1)
**Timeline:** This week
**Effort:** ~10 hours total

### 3. Make Chatbot Discoverable Without Making It Primary
- **Goal:** Augment content, don't replace it
- **Implementation:**
  - Add prominent button near hero: "Ask about our research"
  - Position next to "Start a conversation" for dual-path engagement
  - Keep existing content structure (scanning + interaction)
- **Validation:** A/B test chatbot discovery impact on engagement
- **Why not chatbot-first:** Different users need different entry points (scanning vs conversation)

### 4. Add One Credibility Marker Above the Fold
- **Options (choose one):**
  - "Research by [Name], formerly [Institution/Company]"
  - "Supported by [Grant/Institution]"
  - "Featured in [Publication]"
  - "In collaboration with [Partner]"
- **Goal:** Establish authority in first 3 seconds
- **Placement:** Near hero or immediately below logo

### 5. Clarify What Conversation You Want
- **Replace mailto with structured form:**
  - Name (required)
  - Organization (required)
  - Email (required)
  - **Interest dropdown:**
    - Research collaboration
    - Applied partnership
    - Funding opportunities
    - Something else
  - Message (optional - pre-filled based on dropdown)
- **Benefit:** Guides conversation without heavy qualification
- **Secondary benefit:** Provides data for prioritizing responses

### 10. Build Email Capture for Research Updates
- **Copy:** "Get notified when we publish new research"
- **Value proposition:** Low-commitment connection method
- **Implementation:** Simple email capture (name + email)
- **Positioning:** Footer or dedicated section
- **Why:** Warmer than cold mailto, lighter than collaboration form

---

## Tier 3: Strategic Content Improvements (Month 1)
**Timeline:** 2-4 weeks
**Effort:** 20+ hours

### 6. Rewrite Three Gaps with Problem-First Framing
**Current approach:** Framework → Example
**Better approach:** Problem → Framework → Validation

**For each gap, structure as:**
1. **Concrete scenario** (relatable problem)
2. **Create urgency/doubt** (why this matters now)
3. **Introduce framework** (your solution)
4. **Validation** (how you know it works)

**Example transformation:**

**Current (Gap 1):**
> "Gap 1: Knowledge - Signal vs. Noise. AI treats every output the same way - whether it's reciting established fact or guessing. You can't tell what to trust."

**Improved:**
> "You're making million-dollar decisions based on AI analysis. When the model says it's '85% confident,' what does that mean? Has it been right 85% of the time before? Or is that number just... made up?
>
> Standard AI systems treat every output identically - reciting established facts and creative guesses arrive with the same presentation of certainty. You have no signal about which to trust.
>
> We're researching scenario bands that make uncertainty visible. Instead of a single prediction, show conservative, likely, and optimistic outcomes. The spread between scenarios communicates confidence without requiring you to interpret hedging language."

**Agent task:** Rewrite all three gaps following this pattern

### 7. Add One Detailed Case Study Per Domain
**Goal:** Show research in practice, not just theory
**Format:** Narrative, not metrics

**Structure for each case study:**
- **Challenge:** What problem were we investigating?
- **Approach:** What did we try and why?
- **What we learned:** Insights from the research (not success metrics)
- **Current state:** Where this research stands now
- **Open questions:** What we're still exploring

**Domains:**
- VortexV2: Marine weather forecasting research
- Alpha Arena: Financial intelligence research
- Cortex: Strategic intelligence research

**Note:** Removed metrics correctly - keep narrative focus on learning, not proving

**Agent task:** Draft case study narratives for each domain

---

## Tier 4: Consider Later (Month 2+)
**Timeline:** After validating Tier 1-3 impact
**Effort:** Variable

### 8. Performance Audit with Actual Metrics
- **Don't optimize blindly:** Measure first
- **Metrics needed:**
  - Time to Interactive (mobile/desktop)
  - Animation load impact on engagement
  - Bounce rate correlation with load time
- **A/B test:** Lightweight animation vs current WebGL implementation
- **Decision point:** Only optimize if proven problem
- **Note:** Current 880KB animation may be worth it for aesthetic credibility

### 9. Experiment with Entry Point Content
- **Hypothesis:** Some visitors need faster hook
- **Test:** Single, concrete research question as entry
- **Example:** "Can we predict wind patterns better than ECMWF?" with "Learn how →"
- **Goal:** Faster path for impatient but qualified visitors
- **Validation:** Does this increase engagement without reducing quality?

---

## Implementation Notes

### What Was Actually Done (2026-01-20)

**Tier 1 (Complete):**
- ✅ Fixed EXPLORE button (functional scroll)
- ✅ Added meta description and OpenGraph tags

**Tier 2 (Complete):**
- ✅ Made chatbot discoverable (button in Opening section)
- ✅ Replaced mailto with structured contact form (expandable)
- ✅ Contact form has black background overlay when open

**Tier 3 (Modified):**
- ✅ Three Gaps rewritten with problem-first framing
- ✅ Case studies merged into Three Gaps as expandable examples
  - Instead of separate "Research in Practice" section
  - Each gap card now has EXAMPLE section when expanded
  - Keeps examples close to concepts
  - Cleaner site flow

**Current Site Structure:**
```
Hero → Opening (with chatbot CTA) → Three Gaps (expandable examples) → Footer
```

**Removed Sections:**
- PhilosophyV2 (redundant with Opening/Three Gaps)
- Separate "Research in Practice" section (merged into Three Gaps)
- "Independent Research" credibility line (user requested removal)

### What NOT to Do
1. **Don't make chatbot primary interface** - Destroys scannability and brand impact
2. **Don't replace static content** - Serves different cognitive mode than conversation
3. **Don't optimize for broad SEO** - May attract wrong audience for research partnerships
4. **Don't add time estimates** - Against research teaser principles
5. **Don't re-introduce metrics** - Correctly removed for research framing

### Success Metrics
- **Tier 1:** Zero broken elements, professional link previews
- **Tier 2:** Increased chatbot discovery, structured connection data
- **Tier 3:** Higher engagement on rewritten content, narrative case studies
- **Overall:** More qualified conversations, not more traffic

### Decision Points
1. After Tier 1: Does fixing broken button restore credibility?
2. After Tier 2: Does structured form improve connection quality?
3. After Tier 3: Does problem-first framing increase engagement?
4. Before Tier 4: Do we have enough traffic data to optimize performance?

---

## Related Context
- **Site purpose:** Research teaser for selective partnerships
- **Not:** Commercial product, broad audience acquisition
- **Audience:** Technical decision-makers, research collaborators, potential funders
- **Core tension:** Complexity as filter vs accessibility for time-constrained visitors
- **Design philosophy:** Calibrated intelligence requires calibrated presentation
