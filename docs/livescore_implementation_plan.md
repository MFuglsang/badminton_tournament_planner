# Implementation Plan: Live Scoring and Judge Mobile Scoring

**Date:** June 26, 2026  
**Status:** Planning Phase - No code implementation yet  
**Issue:** MFuglsang/badminton_tournament_planner#30

---

## Executive Summary

This plan outlines a comprehensive implementation strategy for adding live scoring and mobile judge scoring capabilities to the badminton tournament planner. The feature enables judges to submit match results directly from their mobile devices by scanning QR codes on printed score sheets, eliminating the need to enter results manually at the judge's table.

### Key Features
1. **Match UUIDs**: Every match gets a unique identifier for easy URL sharing
2. **System Settings**: Configurable toggles for `live_scoring` and `judge_scoring` features
3. **Mobile-Optimized Interface**: Judge-friendly scoring page for mobile devices
4. **QR Code Generation**: Automatic QR codes on printed score sheets
5. **Real-Time Score Tracking**: Point-by-point score updates (if enabled)
6. **Result Submission & Validation**: Judges submit results from mobile, bypassing judge table entry

---

## Architecture Overview

### Technology Stack
- **Backend**: Django 6.0+ (existing)
- **Database**: SQLite/PostgreSQL (existing)
- **QR Code Generation**: `qrcode` Python library (new)
- **Mobile UI**: HTML5/CSS3 responsive design (new)
- **Real-Time Updates**: WebSockets or polling with JavaScript (new, optional)
- **REST API**: Django REST Framework (new)

### System Components
1. **Data Models**: Match UUID, Settings, Score History, Judge Submissions
2. **Backend Services**: Validation, QR generation, API endpoints
3. **Mobile Frontend**: Responsive judge scoring interface
4. **Score Sheet Integration**: QR codes on existing printouts
5. **Result Management**: Submission workflow and confirmation

---

## Detailed Implementation Plan

### Phase 1: Database Model Updates

#### 1.1 Add UUID to Match Model
**File**: `tournaments/models.py` → `Match` model

**Changes**:
- Add `uuid` field: `UUIDField(default=uuid.uuid4, editable=False, unique=True)`
- Purpose: Create a unique, shareable identifier for each match
- Includes: Auto-generated UUID on match creation
- Migration: Simple AddField migration

**Considerations**:
- UUID is read-only and never manually changed
- Used in URLs: `/match/<uuid>/score/`
- Backward compatible: Existing integer ID still used internally

#### 1.2 Create SystemSettings Model
**File**: Create new model in `tournaments/models.py` or `tournament_planner/models.py`

**Model Definition**:
```python
class SystemSettings(models.Model):
    """Global system-wide feature toggles for live scoring"""
    
    live_scoring_enabled = BooleanField(
        default=False,
        help_text="Enable point-by-point live score tracking during matches"
    )
    judge_scoring_enabled = BooleanField(
        default=False,
        help_text="Enable judges to submit results via mobile"
    )
    
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
```

**Purpose**: Global feature toggles (affects all tournaments)
**Access**: Via singleton pattern or cache
**Admin**: Accessible only to superusers via Django admin

**Alternative Design** (Tournament-level settings):
- Could be moved to Tournament model if per-tournament control is needed
- Add `live_scoring` and `judge_scoring` BooleanFields to Tournament
- Allows flexibility for different tournament types

#### 1.3 Create MatchScoreHistory Model
**File**: `tournaments/models.py`

**Model Definition**:
```python
class MatchScoreHistory(models.Model):
    """Track point-by-point score updates during live scoring"""
    
    match = ForeignKey(Match, on_delete=models.CASCADE)
    timestamp = DateTimeField(auto_now_add=True)
    team1_score = IntegerField()  # Current set score or overall points
    team2_score = IntegerField()
    current_set = IntegerField(default=1)
    event_type = CharField(
        max_length=20,
        choices=[('point', 'Point awarded'), ('set_won', 'Set won'), ('match_end', 'Match ended')]
    )
    submitted_by = ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['match', 'timestamp']
```

**Purpose**: Maintain audit trail of all score changes during live scoring
**Used for**: Display historical score progression, validation, dispute resolution
**Access**: Read-only except for real-time updates

#### 1.4 Create JudgeSubmission Model
**File**: `tournaments/models.py`

**Model Definition**:
```python
class JudgeSubmission(models.Model):
    """Track judge score submissions from mobile devices"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft/In Progress'),
        ('submitted', 'Submitted by Judge'),
        ('validated', 'Validated by System'),
        ('applied', 'Applied to Match'),
        ('rejected', 'Rejected - Invalid'),
    ]
    
    match = ForeignKey(Match, on_delete=models.CASCADE)
    judge_identifier = CharField(max_length=100)  # Judge name/ID for audit
    submission_time = DateTimeField(auto_now_add=True)
    final_score = CharField(max_length=50)  # e.g., "21-15, 18-21, 21-18"
    winner_team = ForeignKey(Team, on_delete=models.SET_NULL, null=True)
    submission_method = CharField(
        max_length=20,
        choices=[('manual', 'Manual Entry'), ('live', 'Live Score Tracking')]
    )
    status = CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_by = ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ip_address = GenericIPAddressField(null=True, blank=True)  # Audit trail
    device_info = TextField(blank=True)  # Mobile device info for support
    comments = TextField(blank=True)  # Notes from judge
    
    class Meta:
        ordering = ['-submission_time']
```

**Purpose**: 
- Track when judges submit results
- Audit trail of all submissions
- Enable dispute resolution
- Validation status tracking

**Migration**: New table

---

### Phase 2: Backend API and Services

#### 2.1 REST API Endpoints (Django REST Framework)

**File**: Create `tournaments/api.py` and register in `tournaments/urls.py`

**Endpoints**:

1. **GET `/api/matches/<uuid>/`** - Get match details
   - Returns: Teams, current score, status, match info
   - Auth: Public (no auth) or token-based (configurable)
   - Response includes: Full match data and current submission status

2. **GET `/api/matches/<uuid>/history/`** - Get score history
   - Returns: All historical score changes (if live_scoring enabled)
   - Auth: Public/token
   - Useful for: Live display during match

3. **POST `/api/matches/<uuid>/live-score/`** - Submit live score update
   - Requires: `judge_id`, `team1_score`, `team2_score`, `current_set`
   - Auth: Token-based (generated from QR code)
   - Rate limiting: Prevent spam
   - Returns: Updated score history and status

4. **POST `/api/matches/<uuid>/final-score/`** - Submit final match result
   - Requires: `judge_id`, `final_score` (string), `winner_uuid`
   - Auth: Token-based
   - Validation: Uses existing BWF score validation
   - Returns: Submission status and confirmation

5. **GET `/api/matches/<uuid>/submission-status/`** - Check submission status
   - Returns: Current submission state, validation errors, next steps
   - Auth: Public

#### 2.2 Authentication Strategy for Judges

**Design Options**:

**Option A: Token-based (Recommended)**
- QR code encodes: Base URL + match UUID + token
- Token generated server-side, unique per match
- Token expires after match completion or time window
- No user login required

**Option B: One-Time Access Codes**
- Short numeric code (e.g., 6-digit) on score sheet
- Judge enters code on first access
- Code validates and creates session

**Option C: No Authentication (Less Secure)**
- Open access to all matches
- Requires CSRF protection
- IP-based rate limiting

**Recommendation**: Option A (token-based) - balances security with ease of use

#### 2.3 Score Validation Service

**File**: Create `tournaments/score_validation.py`

**Functionality**:
- Reuse existing BWF validation (currently in `MatchResultForm`)
- Validate final scores submitted via mobile
- Validate live score progressions
- Return detailed error messages in Danish/English
- Detect impossible score sequences

**Key Function**: `validate_score_submission(score_str, team1_name, team2_name)`

#### 2.4 QR Code Generation Service

**File**: Create `tournaments/qr_service.py`

**Functionality**:
- Generate QR code for each match
- URL format: `https://domain.com/match/<uuid>/score/<token>/`
- Generate image or embedded SVG
- Include match number and teams in QR metadata

**Integration Points**:
- Called when match is created
- Regenerated when needed
- Cached/stored with match

**Library**: `qrcode>=7.4`

---

### Phase 3: Frontend - Mobile Judge Scoring Interface

#### 3.1 Mobile-Optimized HTML Templates

**Files to Create**:

**1. `/tournaments/templates/tournaments/judge_score_entry.html`**
- Mobile-responsive layout (viewport meta tags)
- Two-column score display (Team 1 vs Team 2)
- Large touch-friendly buttons for score input
- Clear match identification (division, round, team names)

**Design Features**:
- Portrait orientation optimized
- Minimal text, large fonts (18pt+)
- High contrast colors for outdoor visibility
- Offline capability (store score locally)
- Auto-save draft scores

**2. `/tournaments/templates/tournaments/judge_live_score.html`**
- Real-time score tracking interface
- Point-by-point input with visual confirmation
- Set progression display
- Match status indicators
- Quick undo/correction buttons

**3. `/tournaments/templates/tournaments/judge_score_confirmation.html`**
- Review submitted score
- Confirm teams and final result
- Allow comment/notes input
- Submit button with confirmation

#### 3.2 Mobile UI/UX Specifications

**Score Entry Modes**:

**Mode A: Manual Entry**
- Judge enters final score as string: "21-15, 18-21, 21-18"
- Validate on blur or explicit validation button
- Error feedback inline
- Selected team confirmed as winner

**Mode B: Live Score Tracking (if enabled)**
- Point-by-point entry during match
- Visual set progression
- Current set and points clearly displayed
- Auto-detect when set/match is complete
- Running score total

**Both Modes**: 
- Judge identifier field (name, ID, badge number)
- Submit with timestamp
- Offline capability (WebStorage)

#### 3.3 JavaScript Implementation

**File**: `tournament_planner/static/js/judge_scoring.js`

**Functionality**:
- Form validation and error handling
- Real-time API calls to backend
- Offline score storage
- Retry logic for failed submissions
- WebSocket connection (if live updates enabled)
- Responsive design breakpoints

**Key Features**:
- Auto-save functionality
- Unsaved changes warning
- Graceful degradation without JavaScript
- Mobile-specific touch handlers

---

### Phase 4: Backend Views and Endpoint Implementation

#### 4.1 Django Views

**File**: `tournaments/views.py` (add new views)

**Views**:

1. **`judge_score_entry(request, match_uuid)`**
   - Renders mobile scoring interface
   - GET: Display scoring form
   - POST: Redirect to confirmation
   - Auth: Public or token-based

2. **`judge_score_confirmation(request, match_uuid)`**
   - Review and confirm submission
   - GET: Display confirmation page
   - POST: Submit final score

3. **`judge_score_result(request, match_uuid)`**
   - Show result after submission
   - Display confirmation message
   - Provide print/share options

#### 4.2 Score Processing Workflow

**When Judge Submits Score**:

1. **Validation Phase**
   - Check score format (via existing BWF validation)
   - Ensure teams match match record
   - Verify no duplicate submissions
   - Validate team selection against final score

2. **Submission Creation**
   - Create JudgeSubmission record with status='draft'
   - Generate token for this submission
   - Store IP address and device info

3. **Confirmation Phase**
   - Judge reviews and confirms
   - Final submission with status='submitted'

4. **Application Phase**
   - Validate one more time
   - Apply to Match model (update `score`, `winner`, `status`)
   - Create MatchScoreHistory entry
   - Notify tournament organizer (optional)

5. **Feedback**
   - Show success message
   - Provide option to print confirmation
   - Display updated standings (if visible)

---

### Phase 5: Score Sheet Integration

#### 5.1 QR Code on Score Sheets

**File**: `tournaments/templates/tournaments/scoresheet.html` (modify)

**Changes**:
- Generate QR code URL for each match
- Display QR code prominently on score sheet
- Add text: "Scan for mobile scoring" (multilingual)
- Include match UUID as fallback text
- Optionally add match number for reference

**QR Code Content**:
```
https://domain.com/match/<match-uuid>/score/<judge-token>/
```

**Visual Design**:
- Large QR code (2"x2" minimum for phone readability)
- Place in corner or header
- Print-friendly (black/white, high contrast)
- Include instructions in Danish

#### 5.2 Score Sheet Template Updates

**Printout Enhancements**:
- Add QR code section
- Add instructions for judges
- Highlight judge information fields
- Note about mobile scoring availability

---

### Phase 6: System Configuration and Admin Interface

#### 6.1 Django Admin Customization

**File**: `tournaments/admin.py` (modify)

**Admin Changes**:
- Add SystemSettings to admin interface
- Add inline MatchScoreHistory display in Match admin
- Add inline JudgeSubmission display in Match admin
- View-only fields for audit trail

**Permission Structure**:
- SystemSettings: Superusers only
- JudgeSubmission: Staff can view, superusers can modify
- MatchScoreHistory: Staff can view (read-only)

#### 6.2 Tournament-Level Configuration (Optional)

**If per-tournament settings desired**:
- Add `live_scoring` and `judge_scoring` BooleanFields to Tournament model
- Override system settings per tournament
- UI toggle in tournament edit form

---

### Phase 7: Testing Strategy

#### 7.1 Unit Tests

**Test Files**: Add to `tournaments/tests.py`

**Test Cases**:

1. **UUID Tests**
   - UUID generated on match creation
   - UUID is unique per match
   - UUID is immutable after creation
   - UUID formats correctly in URLs

2. **Score Validation Tests**
   - Valid scores accepted
   - Invalid scores rejected with proper errors
   - BWF rules enforced (min 21, deuce handling, etc.)
   - Impossible sequences rejected

3. **API Tests**
   - GET match details returns correct data
   - POST live score updates validated
   - POST final score submission works
   - Rate limiting enforced
   - Invalid tokens rejected

4. **JudgeSubmission Tests**
   - Submissions stored correctly
   - Status transitions validated
   - Audit fields populated
   - Duplicate submission detection

5. **QR Code Tests**
   - QR code generated for all matches
   - QR code content correct
   - QR code regeneration works
   - QR codes unique per match

#### 7.2 Integration Tests

**Scenarios**:
- Full judge submission workflow (manual entry)
- Full judge submission workflow (live scoring)
- Score validation and application to match
- Offline submission retry after online return
- Multiple judge submissions rejection (first wins)
- Admin viewing submission history

#### 7.3 Manual Testing Checklist

**Mobile Testing**:
- [ ] QR code scans correctly on various phones
- [ ] Interface responsive on various screen sizes
- [ ] Touch inputs work smoothly
- [ ] Forms submit correctly
- [ ] Offline storage works (no network)
- [ ] Error messages clear and actionable

**User Workflows**:
- [ ] Judge can scan QR from score sheet
- [ ] Judge can enter manual score
- [ ] Judge can track live score point-by-point
- [ ] Judge can review and confirm submission
- [ ] Submission appears in match record
- [ ] Admin can view all submissions
- [ ] Score sheet prints correctly with QR code

---

## Implementation Order (Recommended Sequence)

### Step 1: Foundation (Database & Models)
1. Add UUID to Match model
2. Create SystemSettings model
3. Create MatchScoreHistory model
4. Create JudgeSubmission model
5. Generate and run migrations

**Dependencies**: None  
**Estimated Time**: 2-3 hours  
**Testing**: Unit tests for model creation and validation

### Step 2: API Layer
1. Implement REST API endpoints
2. Implement authentication (token generation)
3. Implement score validation service
4. Implement QR code generation service

**Dependencies**: Step 1 complete  
**Estimated Time**: 4-5 hours  
**Testing**: API endpoint tests

### Step 3: Mobile Frontend Templates
1. Create judge_score_entry.html
2. Create judge_live_score.html
3. Create judge_score_confirmation.html
4. Create supporting CSS for mobile responsiveness

**Dependencies**: Step 2 (API working)  
**Estimated Time**: 4-6 hours  
**Testing**: Manual mobile testing

### Step 4: JavaScript and UX
1. Implement judge_scoring.js with validation
2. Add offline storage capabilities
3. Add error handling and retry logic
4. Optimize for mobile performance

**Dependencies**: Step 3 complete  
**Estimated Time**: 4-6 hours  
**Testing**: Cross-browser mobile testing

### Step 5: Backend Views and Score Processing
1. Implement judge_score_entry view
2. Implement judge_score_confirmation view
3. Implement score submission processing
4. Implement result application workflow

**Dependencies**: Steps 2-4 complete  
**Estimated Time**: 3-4 hours  
**Testing**: Integration tests

### Step 6: Score Sheet Integration
1. Update scoresheet.html template
2. Add QR code generation
3. Update print formatting
4. Add judge instructions

**Dependencies**: Steps 1-2 complete  
**Estimated Time**: 2 hours  
**Testing**: Print testing

### Step 7: Admin Interface
1. Register models in Django admin
2. Customize admin displays
3. Add permission restrictions
4. Create admin views for submissions

**Dependencies**: All previous steps  
**Estimated Time**: 2-3 hours  
**Testing**: Admin interface tests

### Step 8: Comprehensive Testing
1. Write comprehensive unit tests
2. Write integration tests
3. Perform manual QA
4. Load testing if applicable

**Dependencies**: All implementation complete  
**Estimated Time**: 4-6 hours  
**Testing**: Full QA cycle

### Step 9: Documentation and Deployment
1. Update README and user guides (Danish)
2. Document API endpoints
3. Create admin documentation
4. Prepare deployment checklist

**Dependencies**: All features complete  
**Estimated Time**: 2-3 hours

---

## Dependencies and Requirements

### New Python Libraries

**Required Additions to requirements.txt**:
```
qrcode>=7.4              # QR code generation
django-rest-framework>=3.14  # REST API
djangorestframework-simplejwt>=5.2  # JWT tokens (optional, for auth)
```

**Optional Additions**:
```
channels>=3.0    # WebSocket support for real-time updates
```

### Browser/Client Requirements

- HTML5 capable browser
- JavaScript enabled
- Camera access (for QR scanning - can use native phone functionality)
- Responsive design support (viewport meta tags)

### Server Requirements

- Django 6.0+
- Python 3.9+
- HTTPS recommended (for security)

---

## Database Schema Changes

### Migration Plan

**Migration 1**: `add_match_uuid`
```python
# In Match model
uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
```

**Migration 2**: `create_system_settings`
- New SystemSettings table
- Fields: live_scoring_enabled, judge_scoring_enabled

**Migration 3**: `create_match_score_history`
- New MatchScoreHistory table
- Foreign key to Match
- Timestamp tracking

**Migration 4**: `create_judge_submission`
- New JudgeSubmission table
- Foreign keys to Match and Team
- Audit fields (IP, device info, timestamp)

---

## Configuration and Feature Toggles

### System Settings (Django Admin)

**Location**: Django Admin → System Settings

**Fields**:
- `live_scoring_enabled`: Toggle point-by-point score tracking
- `judge_scoring_enabled`: Toggle judge mobile submissions

**Effect**:
- Disabling features removes UI elements
- Backwards compatible (graceful degradation)
- Can be toggled on/off without code changes

### Tournament-Level Override (Optional)

If implemented, add to Tournament model:
- `live_scoring_override`: Allow overriding system setting per tournament
- `judge_scoring_override`: Allow overriding system setting per tournament

---

## Security Considerations

### Authentication & Authorization
1. **Token-based access**: Each match gets unique token
2. **Rate limiting**: Prevent brute force attacks
3. **CSRF protection**: All POST requests protected
4. **HTTPS required**: For production deployment
5. **IP logging**: Audit trail for dispute resolution

### Data Validation
1. **Score format validation**: Strict BWF rules
2. **Team verification**: Ensure teams match match record
3. **Duplicate submission prevention**: Only first valid submission applied
4. **Input sanitization**: Prevent injection attacks

### Privacy
1. **Minimal data collection**: Judge ID only (configurable)
2. **IP logging**: Optional, for audit trail
3. **Device info**: Optional, for support purposes
4. **No unnecessary cookies/tracking**

---

## Rollback and Safety

### If Live Scoring Causes Issues
1. Disable `judge_scoring_enabled` in SystemSettings
2. Mobile interface becomes read-only
3. Existing submissions remain in database
4. Can be re-enabled without data loss

### Data Recovery
1. JudgeSubmission records store all submissions
2. MatchScoreHistory provides audit trail
3. Can revert incorrect submissions via admin
4. Original manual match entry still available

---

## Future Enhancements

**Not in Phase 1, but consider for Phase 2**:

1. **WebSocket Live Updates**
   - Real-time score broadcasting to all clients
   - Uses Django Channels
   - Spectator interface showing live scores

2. **Duplicate Submission Detection**
   - Compare new submission with recent ones
   - Alert if suspiciously similar scores

3. **Analytics Dashboard**
   - Track judge submission rates
   - Measure speed of result reporting
   - Identify problematic matches

4. **Mobile App**
   - Native iOS/Android app
   - Offline capability (sync when online)
   - Biometric unlock for security

5. **Result Dispute Workflow**
   - Organizer review of flagged submissions
   - Judge re-confirmation process
   - Audit trail for disputes

6. **Push Notifications**
   - Notify organizers of submitted scores
   - Confirm successful submissions to judges
   - Remind judges of pending matches

7. **Multi-Language Support**
   - Currently Danish/English
   - Extend to additional languages
   - SMS notifications

---

## Success Criteria

### Phase 1 Complete When:
- ✓ All models implemented and migrated
- ✓ UUID uniqueness verified
- ✓ All API endpoints tested and working
- ✓ Score validation working correctly
- ✓ Mobile interface responsive and usable
- ✓ QR codes generate and print correctly
- ✓ Judge submission workflow end-to-end working
- ✓ Scores correctly applied to match records
- ✓ Unit and integration tests passing (>85% coverage)
- ✓ Manual QA on real mobile devices passed

### Performance Targets:
- API response time: <200ms
- QR code generation: <100ms
- Mobile page load: <2s on 4G
- Form submission: <500ms

---

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Poor mobile UX | Judges won't use feature | Extensive mobile testing, iterate on design |
| Network failures | Lost submissions | Offline storage with sync capability |
| Score validation errors | Incorrect results | Comprehensive validation, judge review step |
| Duplicate submissions | Match confusion | Duplicate detection, first-only policy |
| Security vulnerabilities | Unauthorized access | Token expiration, rate limiting, HTTPS |
| Performance issues | Timeouts on live scoring | Load testing, optimize queries, caching |

---

## Approval and Sign-Off

This implementation plan is ready for:
1. **Review**: By development team leads
2. **Approval**: By project manager/owner
3. **Scheduling**: Resource allocation and timeline
4. **Execution**: Begin Phase 1 implementation

**Next Steps**:
1. Obtain stakeholder approval of this plan
2. Schedule development resources
3. Begin Phase 1 (Database models)
4. Establish sprint schedule
5. Set up branch strategy for development

---

**Document Version**: 1.0  
**Last Updated**: June 26, 2026  
**Status**: Ready for Review and Approval
