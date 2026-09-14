# Implementation Plan: Live Scoring and Judge Mobile Scoring

**Date:** June 26, 2026  
**Status:** Planning Phase - No code implementation yet  
**Issue:** MFuglsang/badminton_tournament_planner#30

---

## Executive Summary

This plan outlines a comprehensive implementation strategy for adding live scoring and mobile judge scoring capabilities to the badminton tournament planner. The feature enables judges to submit match results directly from their mobile devices by scanning QR codes on printed score sheets, eliminating the need to enter results manually at the judge's table.

### Key Features
1. **Match UUIDs**: Every match gets a unique identifier for easy URL sharing
2. **Tournament-Level Feature Configuration**: Each tournament can enable/disable `live_scoring` and `judge_scoring` during setup
3. **Mobile-Optimized Interface**: Judge-friendly scoring page for mobile devices
4. **QR Code Generation**: Automatic QR codes on printed score sheets
5. **Real-Time Score Tracking**: Point-by-point score updates (if enabled)
6. **Result Submission & Validation**: Judges submit results from mobile, bypassing judge table entry
7. **Court Management**: Define courts per tournament and assign them during match execution

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
1. **Data Models**: Match UUID, Tournament Settings, Score History, Judge Submissions, Courts
2. **Backend Services**: Validation, QR generation, API endpoints
3. **Mobile Frontend**: Responsive judge scoring interface
4. **Score Sheet Integration**: QR codes on existing printouts
5. **Result Management**: Submission workflow and confirmation
6. **Tournament Configuration**: Feature toggles during tournament creation

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

#### 1.2 Update Tournament Model with Feature Toggles
**File**: Modify `tournaments/models.py` → `Tournament` model

**Changes**:
```python
# Add to Tournament model:
live_scoring_enabled = BooleanField(
    default=False,
    help_text="Enable point-by-point live score tracking during matches"
)
judge_scoring_enabled = BooleanField(
    default=False,
    help_text="Enable judges to submit results via mobile devices"
)
```

**Purpose**: Per-tournament feature toggles
**Scope**: Each tournament can independently enable/disable features
**Configured**: During tournament creation/edit
**Usage**: 
- `tournament.live_scoring_enabled` - checks if live scoring active
- `tournament.judge_scoring_enabled` - checks if judge scoring active
- Used to show/hide UI elements
- Affects which features are available for that tournament

**Admin & Setup Form**:
- Add checkboxes in Tournament admin: "Enable Live Scoring?", "Enable Judge Scoring?"
- Add to tournament setup wizard
- Default: Both disabled (opt-in feature)
- Can be changed anytime (before or during tournament)

**Advantages**:
- Different tournaments, different needs
- Easy to test features on one tournament before enabling globally
- Simple configuration, no need for complex admin interface
- Stored per tournament (no global settings model needed)

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

#### 1.5 Create Court Management Models

**File**: `tournaments/models.py`

**Model 1: TournamentCourt**
```python
class TournamentCourt(models.Model):
    """Define available courts for a specific tournament"""
    
    tournament = ForeignKey(Tournament, on_delete=models.CASCADE, related_name='courts')
    court_number = IntegerField(help_text="Court identifier (e.g., 1, 2, 3, etc.)")
    court_name = CharField(
        max_length=100,
        blank=True,
        help_text="Optional descriptive name (e.g., 'Hall A - Court 1')"
    )
    location = CharField(
        max_length=255,
        blank=True,
        help_text="Physical location or hall (e.g., 'Sporthallen - Sal 1')"
    )
    is_active = BooleanField(
        default=True,
        help_text="Disable court without deleting historical data"
    )
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('tournament', 'court_number')
        ordering = ['court_number']
        verbose_name = "Tournament Court"
        verbose_name_plural = "Tournament Courts"
    
    def __str__(self):
        if self.court_name:
            return f"{self.tournament.name} - {self.court_name}"
        return f"{self.tournament.name} - Court {self.court_number}"
```

**Purpose**:
- Define which courts/baner are available for each tournament
- Manage court numbers centrally
- Allow multiple tournaments to have different court setups
- Support both simple numbering (1, 2, 3) and descriptive names

**Key Features**:
- `court_number`: Primary identifier (used for validation)
- `court_name`: Optional descriptive name for display
- `location`: Physical location info (which hall/area)
- `is_active`: Soft delete capability
- Unique constraint: Only one court per number per tournament

**Model 2: MatchCourt**
```python
class MatchCourt(models.Model):
    """Track court assignment for matches"""
    
    match = OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name='court_assignment',
        null=True,
        blank=True
    )
    tournament_court = ForeignKey(
        TournamentCourt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='match_assignments'
    )
    assigned_at = DateTimeField(auto_now_add=True)
    assigned_by = ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text="User who assigned the court"
    )
    match_started = BooleanField(
        default=False,
        help_text="Was court assigned when match started"
    )
    notes = TextField(
        blank=True,
        help_text="Optional notes about the court assignment"
    )
    
    class Meta:
        verbose_name = "Match Court Assignment"
        verbose_name_plural = "Match Court Assignments"
```

**Purpose**:
- Track which court is assigned to each match
- Store audit information (when assigned, by whom)
- Allow assignment to happen just before match starts
- Support optional notes about assignments

**Key Features**:
- `match`: One-to-one relationship (each match has max one court)
- `tournament_court`: Reference to predefined court
- `assigned_at`: Timestamp of assignment
- `assigned_by`: User who made the assignment
- `match_started`: Flag for audit trail
- Allows null (court can be unassigned)

**Migration**: Two new tables

**Validation Rules**:
- Cannot assign court from different tournament than the match
- Cannot assign court if already assigned to another active match
- Can only assign active courts (is_active=True)

---

### Phase 1B: Court Management Setup (New Feature)

#### 1B.1 Tournament Setup - Courts & Scoring Features

**File**: Modify `tournaments/admin.py` and `tournaments/views.py`

**Tournament Creation/Edit - New Configuration Section**: "Match Execution Settings"

**Configuration Options**:
1. **Court Management**:
   - New step in tournament wizard: "Configure Available Courts"
   - Form: Court number (required), Court name (optional), Location (optional)
   - Allow adding courts one by one or bulk import
   - Table view: `Court Number | Name | Location | Active`
   - Add/Edit/Delete buttons for courts
   - Validation: Court numbers must be unique within tournament

2. **Scoring Features** (new):
   - Checkbox: "Enable Judge Scoring?" (judges submit scores via mobile)
   - Checkbox: "Enable Live Scoring?" (point-by-point tracking)
   - Help text explaining what each feature does
   - Default: Both unchecked (opt-in)

**Admin Interface Changes**:
- Add inline `TournamentCourt` editing in Tournament admin
- Display active courts with court numbers and names
- Add checkboxes for `judge_scoring_enabled` and `live_scoring_enabled`
- Allow easy add/edit/delete of courts and features

**User-Facing Tournament Setup Page**:
- Include courts configuration section
- Include scoring features toggles section
- All configured together during tournament creation
- Clear indication of which features are enabled

**Example Setup**:
```
Tournament: Danish Open Badminton 2026

Courts:
  - Court 1: Sporthallen - Sal 1
  - Court 2: Sporthallen - Sal 2
  - Court A: Kulturhuset - Sal 1

Scoring Features:
  ✓ Enable Judge Scoring (judges submit results via mobile)
  ☐ Enable Live Scoring (point-by-point tracking)
```
```
Tournament: Danish Open Badminton 2026
Courts:
  - Court 1: Sporthallen - Sal 1
  - Court 2: Sporthallen - Sal 2
  - Court 3: Sporthallen - Sal 3
  - Court A: Kulturhuset - Sal 1
  - Court B: Kulturhuset - Sal 2
```

#### 1B.2 Match Court Assignment Interface

**File**: Modify match detail views or create new `tournaments/assign_court.html`

**Location Options** (choose one or implement both):

**Option A: In Match Detail View**
- Add court assignment section to existing match detail page
- Dropdown showing available courts (from TournamentCourt)
- Assign button next to dropdown
- Display current assignment (if any)
- Show "Not assigned" if no court yet

**Option B: Dedicated Court Assignment Page**
- New page: `/match/<id>/assign-court/`
- Mobile-friendly interface
- Court selection with visual feedback
- Confirmation before assignment
- Show match details clearly (teams, time)

**Option C: Bulk Court Assignment**
- View showing all matches in a round
- Interactive court assignment for multiple matches at once
- Drag-and-drop or form-based assignment
- Useful for tournament organizers to assign all courts before start

**Recommended**: Option A (integrated into match detail) + Option C (bulk assignment)

**Assignment Workflow**:
1. When match is about to start, organizer clicks "Start Match" or similar
2. System displays dropdown of available courts (not already assigned to active matches)
3. Organizer selects court and clicks "Assign" or "Start Match"
4. System validates:
   - Court exists in tournament
   - Court is not assigned to another match
   - Court is active
5. On success:
   - MatchCourt record created
   - Assigned timestamp set
   - User recorded as assigner
   - Feedback: "Court X assigned to [Match]"
6. Court now visible in:
   - Judge scoring interface
   - Match execution screens
7. On error:
   - Clear error message
   - Show alternative available courts

**Reassignment Capability**:
- Allow changing court assignment before match starts
- Once match starts (match_started=True in MatchCourt), prevent reassignment
- Or: Allow reassignment with confirmation warning

#### 1B.3 Court Assignment API Endpoints

**File**: Add to `tournaments/api.py`

**Endpoints**:

1. **GET `/api/tournaments/<id>/courts/`** - List available courts
   - Returns: All active courts for tournament
   - Filter: Only active courts (is_active=True)
   - Auth: Public or logged-in users
   - Response: `[{court_number, court_name, location, assigned_to_matches: [...]}, ...]`

2. **GET `/api/tournaments/<id>/courts/available/`** - List unassigned courts
   - Returns: Courts not currently assigned to active matches
   - Excludes: Courts assigned to matches not yet completed
   - Useful for: Populating assignment dropdowns
   - Response: Same as above but filtered

3. **POST `/api/matches/<id>/assign-court/`** - Assign court to match
   - Requires: `court_id` (or `court_number` + `tournament_id`)
   - Auth: Staff/organizer only
   - Validation: 
     - Court belongs to match's tournament
     - Court not assigned to another match
     - Court is active
   - Returns: Assigned court info + timestamp
   - Creates: MatchCourt record

4. **DELETE `/api/matches/<id>/court/`** - Unassign court
   - Requires: Match has court assigned
   - Auth: Staff/organizer only
   - Only before match starts (configurable)
   - Returns: Success message

5. **GET `/api/matches/<id>/court/`** - Get court assignment for match
   - Returns: Court info or 404 if not assigned
   - Includes: Court number, name, assigned_at, assigned_by
   - Public access (for display during match)

**Court Availability Logic**:
```python
# Court is considered "available" if:
- is_active == True
- No active match assignment exists
  (match not completed AND match not abandoned)
```

#### 1B.4 Display Court on Match Views

**Files to Modify**:

**For Match Execution Interface** (when starting match):
- Show court assignment section
- Allow court selection from available courts
- Display assigned court prominently
- Allow reassignment if needed

**For Live Scoring Interface** (`judge_score_entry.html`):
- Display assigned court number prominently
- Helps judge verify correct court/match
- Useful for match identification during execution

---



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
- Add `judge_scoring_enabled` and `live_scoring_enabled` toggles to Tournament admin
- Add inline `TournamentCourt` editing in Tournament admin
- Add inline `MatchCourt` display in Match admin
- Add inline `MatchScoreHistory` display in Match admin
- Add inline `JudgeSubmission` display in Match admin
- View-only fields for audit trail

**Permission Structure**:
- Tournament feature toggles: Staff can edit
- Tournament courts: Staff can manage
- JudgeSubmission: Staff can view, superusers can modify
- MatchScoreHistory: Staff can view (read-only)
- MatchCourt: Staff can view and assign (read/write for assignments)

#### 6.2 Tournament-Level Configuration

**Already implemented in Phase 1B**:
- Feature toggles (judge_scoring, live_scoring) in Tournament model
- Court configuration in Tournament model
- Both configured in tournament setup wizard

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

## Project Phases Overview

The implementation is divided into 5 distinct phases, each providing incremental value and building on previous phases:

```
FASE 1 (Database & API Foundation)        [2-3 uger]
├─ Database models + migrations
├─ REST API endpoints
└─ Authentication + validation

    ↓

FASE 2 (Court Management Feature)         [1-2 uger]  ← New, for match execution
├─ Tournament court configuration
├─ Court assignment when match starts
└─ Display court in judge interface

    ↓

FASE 3 (Judge Scoring Interface)          [2-3 uger]  ← Ready for testing
├─ Mobile templates (HTML/CSS)
├─ Score entry JavaScript
└─ Judge submission workflow

    ↓

FASE 4 (Integration & Printing)           [1-2 uger]
├─ QR code generation
├─ Score sheets with courts
└─ Admin interface

    ↓

FASE 5 (Testing & Refinement)             [1-2 uger]
├─ Comprehensive testing
├─ Performance optimization
└─ Deployment & documentation
```

---

## Detailed Phase Breakdown

### FASE 1: Database & API Foundation (Weeks 1-3)

**Outcome**: Fully functional REST API with authentication, ready for frontend development. Tournament-level feature toggles working.

**Tasks**:
- ✓ Add UUID to Match model
- ✓ Add judge_scoring_enabled and live_scoring_enabled to Tournament model
- ✓ Create MatchScoreHistory model
- ✓ Create JudgeSubmission model
- ✓ Create TournamentCourt & MatchCourt models
- ✓ Implement all REST API endpoints
- ✓ Implement token-based authentication
- ✓ Implement score validation service
- ✓ Implement QR code generation service
- ✓ Add feature toggles to Tournament admin and setup form
- ✓ Run migrations

**Dependencies**: None

**Testing Required**:
- Unit tests for all models
- API endpoint tests
- Score validation tests
- Authentication tests
- Feature toggle tests

**Deliverables**:
- 6 migrations successfully applied
- API documented (endpoints working)
- Authentication flow tested
- Tournament setup includes scoring feature toggles
- Ready for frontend development

**Can be done by**: Backend developer + Database engineer

---

### FASE 2: Court Management Feature (Weeks 4-5)

**Outcome**: Tournament organizers can define courts and assign them to matches just before start

**Tasks**:
- ✓ Add court configuration to admin interface
- ✓ Create court management in tournament setup form
- ✓ Implement court assignment API endpoints
- ✓ Create court assignment UI (integrated in match detail/match start interface)
- ✓ Validation: prevent duplicate assignments
- ✓ Show assigned court in judge scoring interface (for match execution only)

**Dependencies**: Phase 1 complete

**Testing Required**:
- Integration tests for court workflow
- UI testing for court assignment
- API tests for court endpoints

**Deliverables**:
- Tournament admins can define courts in setup
- Courts can be assigned when match starts (not in schedule/planning)
- Court info visible in judge scoring interface
- Ready for judge integration in Phase 3

**Can be done by**: Full-stack developer

---

### FASE 3: Judge Scoring Interface (Weeks 6-8)

**Outcome**: Judges can submit match scores from mobile devices with full workflow

**Tasks**:
- ✓ Create mobile-responsive HTML templates
  - judge_score_entry.html (manual entry)
  - judge_live_score.html (point-by-point)
  - judge_score_confirmation.html (review)
- ✓ Implement JavaScript validation & error handling
- ✓ Add offline storage capability
- ✓ Implement backend views for scoring
- ✓ Implement score submission workflow
- ✓ Implement score application to matches

**Dependencies**: Phase 1 complete, Phase 2 optional but recommended

**Testing Required**:
- Mobile device testing (various phone sizes)
- Offline/online sync testing
- End-to-end workflow testing
- Judge user acceptance testing

**Deliverables**:
- Mobile interface fully functional
- Judges can scan QR and submit scores
- Scores applied to match records
- Offline capability working

**Can be done by**: Frontend developer + Backend developer

---

### FASE 4: Integration & Printing (Weeks 9-10)

**Outcome**: Score sheets print with QR codes, admin interface fully configured

**Tasks**:
- ✓ Integrate QR codes into score sheet template
- ✓ Add court number to printed score sheets
- ✓ Add print instructions for judges
- ✓ Customize Django admin for submissions
- ✓ Add permission restrictions
- ✓ Create submission review interface

**Dependencies**: Phase 1-3 complete

**Testing Required**:
- Print testing on various printers
- QR code scanning tests
- Admin interface testing
- Score sheet usability testing

**Deliverables**:
- Score sheets print with QR codes + court numbers
- Admin can review all submissions
- Audit trail visible
- Tournament ready for live use

**Can be done by**: Backend developer + UI designer

---

### FASE 5: Testing & Refinement (Weeks 11-12)

**Outcome**: Production-ready system with full documentation

**Tasks**:
- ✓ Comprehensive unit test suite (>85% coverage)
- ✓ Integration tests for all workflows
- ✓ Performance testing & optimization
- ✓ Load testing if applicable
- ✓ Manual QA on real hardware
- ✓ Documentation updates
- ✓ Admin documentation
- ✓ User guide in Danish
- ✓ Deployment checklist

**Dependencies**: Phase 1-4 complete

**Testing Required**:
- Full system regression testing
- Load testing (multiple judges submitting)
- Real tournament dry-run
- Edge case testing

**Deliverables**:
- All tests passing
- 85%+ code coverage
- Documentation complete
- Ready for production deployment

**Can be done by**: QA engineer + Tech lead + Backend developers

---

## Implementation Order (Recommended Sequence)

## Implementation Order (Recommended Sequence) - Detailed Steps

### **FASE 1: Foundation**

#### Step 1.1: Database Models & Migrations
1. Add UUID to Match model
2. Add judge_scoring_enabled and live_scoring_enabled fields to Tournament model
3. Create MatchScoreHistory model
4. Create JudgeSubmission model
5. Create TournamentCourt model
6. Create MatchCourt model
7. Generate and run migrations

**Estimated Time**: 2-3 hours  
**Testing**: Unit tests for model creation

#### Step 1.2: REST API Endpoints
1. Implement `/api/matches/<uuid>/` endpoint
2. Implement `/api/matches/<uuid>/history/` endpoint
3. Implement `/api/matches/<uuid>/live-score/` endpoint
4. Implement `/api/matches/<uuid>/final-score/` endpoint
5. Implement `/api/matches/<uuid>/submission-status/` endpoint
6. Implement court-related endpoints

**Estimated Time**: 3-4 hours  
**Testing**: API endpoint tests with mock data

#### Step 1.3: Services & Validation
1. Implement token-based authentication service
2. Implement score validation service
3. Implement QR code generation service
4. Add rate limiting

**Estimated Time**: 2-3 hours  
**Testing**: Service unit tests

---

### **FASE 2: Court Management**

#### Step 2.1: Admin Interface & Configuration
1. Implement tournament court configuration in admin
2. Add court management to tournament setup form
3. Create court list/edit views

**Estimated Time**: 2 hours  
**Testing**: Admin interface tests

#### Step 2.2: Court Assignment & Display
1. Create court assignment API endpoints
2. Create court assignment UI (in match detail)
3. Add court display to schedules
4. Add validation for assignments

**Estimated Time**: 2 hours  
**Testing**: Integration tests

#### Step 2.3: UI Updates
1. Add court assignment capability in match start/execution interface
2. Display assigned court in judge scoring interface
3. Allow court reassignment if needed before match starts

**Estimated Time**: 1 hour  
**Testing**: UI testing

---

### **FASE 3: Judge Scoring**

#### Step 3.1: Mobile Frontend Templates
1. Create judge_score_entry.html
2. Create judge_live_score.html
3. Create judge_score_confirmation.html
4. Add mobile-responsive CSS

**Estimated Time**: 3-4 hours  
**Testing**: Manual mobile testing

#### Step 3.2: JavaScript & UX
1. Implement judge_scoring.js
2. Add form validation
3. Add offline storage (LocalStorage)
4. Add error handling & retry logic
5. Optimize for mobile

**Estimated Time**: 3-4 hours  
**Testing**: Cross-browser testing

#### Step 3.3: Backend Views & Workflow
1. Implement judge_score_entry view
2. Implement judge_score_confirmation view
3. Implement score submission processing
4. Implement result application to match

**Estimated Time**: 2-3 hours  
**Testing**: Integration tests

---

### **FASE 4: Integration**

#### Step 4.1: QR Code Integration
1. Add QR code generation to score sheets
2. Update scoresheet.html template
3. Add print styling

**Estimated Time**: 1-2 hours  
**Testing**: Print testing

#### Step 4.2: Admin Interface
1. Register models in Django admin
2. Add MatchScoreHistory inline display
3. Add JudgeSubmission inline display
4. Create submission review views
5. Add permission restrictions

**Estimated Time**: 2 hours  
**Testing**: Admin tests

#### Step 4.3: Documentation Updates
1. Update score sheets instructions
2. Add judge guidelines
3. Add admin documentation

**Estimated Time**: 1 hour

---

### **FASE 5: Testing & Refinement**

#### Step 5.1: Comprehensive Testing
1. Write unit tests (>85% coverage)
2. Write integration tests
3. Perform manual QA

**Estimated Time**: 4-6 hours

#### Step 5.2: Optimization & Refinement
1. Performance optimization
2. Load testing
3. Edge case handling
4. Bug fixes

**Estimated Time**: 2-4 hours

#### Step 5.3: Documentation & Deployment
1. Write README updates
2. Create deployment checklist
3. Prepare production deployment

**Estimated Time**: 2-3 hours

---

## Timeline Summary

| Phase | Duration | Start | End | Key Output |
|-------|----------|-------|-----|-----------|
| Phase 1: Foundation | 2-3 weeks | Week 1 | Week 3 | API working, ready for frontend |
| Phase 2: Courts | 1-2 weeks | Week 4 | Week 5 | Banetildeling funktionel |
| Phase 3: Judge UI | 2-3 weeks | Week 6 | Week 8 | Mobile scoring ready |
| Phase 4: Integration | 1-2 weeks | Week 9 | Week 10 | QR codes, admin ready |
| Phase 5: Testing | 1-2 weeks | Week 11 | Week 12 | Production-ready |
| **Total** | **8-12 weeks** | | | **Full system deployed** |

---

## Phase Dependencies Diagram

```
Phase 1 (Database & API)
    ├─ Must complete before: Phase 2, 3, 4, 5
    └─ Duration: 2-3 weeks

Phase 2 (Court Management)
    ├─ Depends on: Phase 1
    ├─ Can run in parallel with: Phase 3
    └─ Duration: 1-2 weeks

Phase 3 (Judge UI)
    ├─ Depends on: Phase 1
    ├─ Can run in parallel with: Phase 2
    └─ Duration: 2-3 weeks

Phase 4 (Integration)
    ├─ Depends on: Phase 1, 2, 3
    ├─ Cannot start until: All previous phases done
    └─ Duration: 1-2 weeks

Phase 5 (Testing)
    ├─ Depends on: Phase 1, 2, 3, 4
    ├─ Cannot start until: All previous phases done
    └─ Duration: 1-2 weeks
```

**Optimization Opportunity**: 
- Phase 2 and Phase 3 can run in parallel if you have 2+ developers
- This could reduce total timeline from 12 weeks to ~8 weeks

---

## Which Phase to Start With?

### Recommended Approach: Phase 1 + Phase 2 First

**Why?**
1. Phase 1 is foundational - nothing else works without it
2. Phase 2 (court management) is new and exciting
3. Phase 2 is independent of Phase 3
4. By doing both early, you have:
   - Database infrastructure ready
   - API ready
   - Court feature working
   - Ready for Phase 3 frontend work

### Alternative: MVP-Focused Approach

If you want to get to a working system faster:
- **MVP 1 (Court Management only)**
  - Do Phase 1 + Phase 2 only
  - ~3-4 weeks
  - Get courts working, manual score entry only
  
- **MVP 2 (Add Judge Scoring)**
  - Add Phase 3 + Phase 4
  - ~4-5 weeks more
  - Full mobile scoring ready
  
- **MVP 3 (Polish & Deploy)**
  - Add Phase 5
  - ~1-2 weeks more
  - Production ready

---

## Resources Needed by Phase

| Phase | Backend | Frontend | DevOps | QA | Total |
|-------|---------|----------|--------|----|---------| 
| Phase 1 | 1 | - | 0.5 | 0.5 | 2 person-weeks |
| Phase 2 | 1 | 0.5 | - | 0.5 | 2 person-weeks |
| Phase 3 | 1 | 1 | - | 0.5 | 2.5 person-weeks |
| Phase 4 | 0.5 | 0.5 | 0.5 | 0.5 | 2 person-weeks |
| Phase 5 | 0.5 | 0.5 | 0.5 | 2 | 3.5 person-weeks |
| **Total** | **4** | **2.5** | **1.5** | **4** | **~12 person-weeks** |

---

## Minimum Viable Product (MVP) Options

### Option A: Court Management Only
**Phases**: 1 + 2  
**Timeline**: 3-4 weeks  
**Features**:
- Define courts per tournament
- Assign courts to matches when they start (execution phase)
- See assigned court in judge interface
- Manual score entry (existing system)

**Value**: Immediate operational benefit for tournament execution

---

### Option B: Court Management + Manual Judge Scoring
**Phases**: 1 + 2 + 3 + 4 (minus live scoring)  
**Timeline**: 6-7 weeks  
**Features**:
- Everything in Option A
- Judges submit final scores via QR code
- Scores applied automatically
- Score sheets print with QR codes + courts

**Value**: Faster score submission, reduced data entry errors

---

### Option C: Full Live Scoring System
**Phases**: 1 + 2 + 3 + 4 + 5  
**Timeline**: 10-12 weeks  
**Features**:
- Everything in Option B
- Point-by-point live scoring
- Real-time score history
- Fully tested and optimized

**Value**: Complete tournament management system with live capabilities

---

## Success Criteria by Phase

### Phase 1 Success
- ✓ All migrations applied successfully (including feature toggle fields on Tournament)
- ✓ API endpoints tested and working
- ✓ Authentication flow functional
- ✓ Score validation service tested
- ✓ QR code generation working
- ✓ Feature toggles (judge_scoring_enabled, live_scoring_enabled) working on Tournament model
- ✓ Tournament admin shows feature toggles
- ✓ Feature toggles accessible in tournament setup form

### Phase 2 Success
- ✓ Courts can be defined in tournament setup
- ✓ Courts can be assigned to matches when they start
- ✓ No duplicate court assignments possible
- ✓ Assigned court visible in judge scoring interface
- ✓ Court info shows on judge execution screen

### Phase 3 Success
- ✓ Mobile interface responsive on various devices
- ✓ Judges can scan QR and submit scores
- ✓ Offline submission capability working
- ✓ Scores applied to match records correctly
- ✓ Error handling and validation working

### Phase 4 Success
- ✓ QR codes print on score sheets
- ✓ QR codes scan correctly
- ✓ Admin can review all submissions
- ✓ Audit trail complete and viewable
- ✓ Score sheets include court information

### Phase 5 Success
- ✓ >85% code coverage
- ✓ All tests passing
- ✓ Performance targets met
- ✓ Documentation complete
- ✓ Real tournament dry-run successful

---

## Implementation Order (Recommended Sequence)

### Step 1: Foundation (Database & Models)
1. Add UUID to Match model
2. Add judge_scoring_enabled and live_scoring_enabled to Tournament model
3. Create MatchScoreHistory model
4. Create JudgeSubmission model
5. Create TournamentCourt model
6. Create MatchCourt model
7. Generate and run migrations

**Dependencies**: None  
**Estimated Time**: 2-3 hours  
**Testing**: Unit tests for model creation and validation

### Step 1B: Court Management (New Feature)
1. Implement tournament court configuration in admin
2. Add court management to tournament setup form
3. Implement court assignment API endpoints
4. Create court assignment UI (integrated in match detail)
5. Add court display to schedules and match views
6. Update score sheets to show assigned courts

**Dependencies**: Step 1 complete  
**Estimated Time**: 3-4 hours  
**Testing**: Integration tests for court assignment workflow

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

### Database Schema Changes

### Migration Plan

**Migration 1**: `add_match_uuid`
```python
# In Match model
uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
```

**Migration 2**: `add_tournament_scoring_features`
```python
# In Tournament model
judge_scoring_enabled = BooleanField(default=False)
live_scoring_enabled = BooleanField(default=False)
```

**Migration 3**: `create_match_score_history`
- New MatchScoreHistory table
- Foreign key to Match
- Timestamp tracking

**Migration 4**: `create_judge_submission`
- New JudgeSubmission table
- Foreign keys to Match and Team
- Audit fields (IP, device info, timestamp)

**Migration 5**: `create_tournament_court`
- New TournamentCourt table
- Foreign key to Tournament
- Fields: court_number, court_name, location, is_active
- Unique constraint on (tournament, court_number)

**Migration 6**: `create_match_court`
- New MatchCourt table
- One-to-one relationship to Match
- Foreign key to TournamentCourt
- Audit fields: assigned_at, assigned_by, match_started
- Optional relationship (nullable fields)

---

## Configuration and Feature Toggles

### Tournament-Level Configuration

**Location**: Tournament Admin / Tournament Setup Wizard

**Fields**:
- `live_scoring_enabled`: Toggle point-by-point score tracking for this tournament
- `judge_scoring_enabled`: Toggle judge mobile submissions for this tournament

**Configuration When**:
- During tournament creation
- Can be modified anytime (before or during tournament)

**Effect**:
- Each tournament independently enables/disables features
- Disabling features removes UI elements for that tournament
- Other tournaments unaffected
- Backwards compatible (graceful degradation)
- Can be toggled on/off without code changes

**Example Tournament Configurations**:
- Tournament A: Judge Scoring ON, Live Scoring OFF (quick result submission)
- Tournament B: Judge Scoring ON, Live Scoring ON (full tracking)
- Tournament C: Judge Scoring OFF, Live Scoring OFF (manual entry only)

**Advantages**:
- Test features on one tournament before enabling widely
- Different tournaments, different needs
- Simple per-tournament control without complex admin
- No need for global settings model

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

### If Live Scoring Causes Issues for a Tournament
1. Go to Tournament admin
2. Disable `judge_scoring_enabled` and/or `live_scoring_enabled` for that tournament
3. Mobile interface becomes unavailable or read-only for that tournament
4. Other tournaments unaffected
5. Existing submissions remain in database
6. Can be re-enabled without data loss

### If Scoring Causes Issues for All Tournaments
1. Disable feature toggles on individual tournaments
2. No global toggle needed - granular control per tournament
3. Can disable on tournament-by-tournament basis

### Data Recovery
1. JudgeSubmission records store all submissions
2. MatchScoreHistory provides audit trail
3. Can revert incorrect submissions via admin
4. Original manual match entry still available

---

## Future Enhancements

**Not in Phase 1, but consider for Phase 2**:

1. **Advanced Court Management**
   - Court availability calendar
   - Court maintenance scheduling
   - Court unavailability blocks
   - Automatic court assignment algorithm
   - Court utilization analytics

2. **WebSocket Live Updates**
   - Real-time score broadcasting to all clients
   - Uses Django Channels
   - Spectator interface showing live scores

3. **Duplicate Submission Detection**
   - Compare new submission with recent ones
   - Alert if suspiciously similar scores

4. **Analytics Dashboard**
   - Track judge submission rates
   - Measure speed of result reporting
   - Identify problematic matches
   - Court utilization tracking

5. **Mobile App**
   - Native iOS/Android app
   - Offline capability (sync when online)
   - Biometric unlock for security

6. **Result Dispute Workflow**
   - Organizer review of flagged submissions
   - Judge re-confirmation process
   - Audit trail for disputes

7. **Push Notifications**
   - Notify organizers of submitted scores
   - Confirm successful submissions to judges
   - Remind judges of pending matches
   - Court assignment notifications

8. **Multi-Language Support**
   - Currently Danish/English
   - Extend to additional languages
   - SMS notifications

---

## Success Criteria

### Phase 1 Complete When:
- ✓ All models implemented and migrated (including court models)
- ✓ UUID uniqueness verified
- ✓ All API endpoints tested and working (including court endpoints)
- ✓ Score validation working correctly
- ✓ Mobile interface responsive and usable
- ✓ QR codes generate and print correctly
- ✓ Judge submission workflow end-to-end working
- ✓ Scores correctly applied to match records
- ✓ Unit and integration tests passing (>85% coverage)
- ✓ Manual QA on real mobile devices passed

### Phase 1B (Court Management) Complete When:
- ✓ Tournament court configuration working in admin
- ✓ Courts can be defined in tournament setup
- ✓ Court assignment to matches working (API + UI)
- ✓ Court information displays on schedules and match details
- ✓ Court numbers show on score sheets
- ✓ Validation prevents duplicate court assignments
- ✓ API endpoints tested for court management
- ✓ Integration tests for court assignment workflow passing

### Performance Targets:
- API response time: <200ms (including court queries)
- QR code generation: <100ms
- Mobile page load: <2s on 4G
- Form submission: <500ms
- Court assignment: <300ms (quick dropdown population)

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
| Court assignment conflicts | Multiple matches assigned same court | Database unique constraints, validation on assignment |
| Forgotten court assignments | Match starts without court | Prompt user to assign court before match starts |
| Wrong court assigned | Judges/players in wrong location | Clear court info in judge interface, allow reassignment |

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
