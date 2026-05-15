# Smart Classroom Dashboard - Quick Reference Guide

## 🏠 Dashboard Overview

Your new dashboard is a all-in-one monitoring center for classroom supervision. Here's what you see:

---

## 📍 Dashboard Sections (Top to Bottom)

### 1. **Alerts & Warnings Section** (Top)
This is your critical information area. You'll see:

#### 🔴 Danger Alert (if any classroom is flagged)
```
⚠️ DANGER ALERT - IMMEDIATE ACTION REQUIRED
Critical Issue: [Classroom Name] is flagged with danger alerts
Please review the status and take corrective measures immediately.
```
- Red banner with white text
- Shows which classrooms need attention
- Dismissible with X button

#### 🟡 Warning Alert (if temperature out of range)
```
⚠️ WARNING - TEMPERATURE OUT OF RANGE
Notice: [Classroom Name] (25°C) has temperature concerns
Adjust HVAC settings to maintain comfortable working conditions (18-26°C recommended).
```
- Yellow banner with dark text
- Shows temperature readings
- Helps with HVAC management

#### 🟢 Success Alert (when all normal)
```
✓ All Systems Operating Normally
All classrooms are functioning properly. No warnings or alerts at this time.
```
- Green banner when everything is fine

---

### 2. **Welcome Section**
- Personalized greeting: "Welcome back, Supervisor"
- Shows total classrooms and students
- Displays today's date and attendance count
- Quick button to "View All Classrooms"

---

### 3. **Key Metrics Cards (Top Right)**
Quick stats at a glance:

| Metric | Meaning |
|--------|---------|
| **Average Occupancy %** | How full classrooms are on average |
| **Busy Classrooms** | How many rooms are over 70% full (X/Total) |
| **Peak Hours** | What time has the most activity (e.g., "10:00-11:00 with 45 sessions") |

---

### 4. **Real-Time Classroom Status Cards**
Each classroom has its own card showing:

```
┌─────────────────────────────┐
│ CLASSROOM NAME         🟢 NORMAL │
├─────────────────────────────┤
│ Occupancy: ████░░░░ 45/100 │
│ 💡 Lights: ON               │
│ 📹 Projector: OFF           │
│ 🚪 Door: CLOSED             │
│ 🌡️ Temperature: 22°C         │
│                             │
│ [View Details]              │
└─────────────────────────────┘
```

**Color Meanings:**
- 🟢 **Green Border** = Normal occupancy (<70%)
- 🟡 **Yellow Border** = Medium occupancy (70-90%)
- 🔴 **Red Border** = High occupancy (>90%) or danger alert

**What Each Shows:**
- Occupancy bar fills as classroom fills with people
- Equipment status (on/off for lights and projector)
- Door status (open/closed)
- Current temperature
- Status badge at top right

---

### 5. **Today's Activity Chart (Hourly)**
Line chart showing:
- X-axis: Hours of the day (00:00 to 23:00)
- Y-axis: Number of attendance sessions
- Shows when classrooms are most used throughout the day
- Helps identify peak hours and quiet periods

**Example Reading:**
- 08:00: 12 sessions (classes starting)
- 14:00: 25 sessions (peak learning time)
- 18:00: 3 sessions (evening winding down)

---

### 6. **Weekly Trend Chart (7 Days)**
Line chart showing:
- X-axis: Days of the week (Mon, Tue, Wed...)
- Y-axis: Total attendance sessions per day
- Shows patterns across the week
- Helps with resource planning

**What It Tells You:**
- Which days are busiest (usually Mon-Wed)
- Weekend activity level
- Consistency of usage

---

### 7. **Weekly Classroom Usage Chart**
Bar chart showing:
- X-axis: Days of the week
- Y-axis: Number of classrooms actively used
- Shows how many different classrooms are in use each day

**Example:**
- Monday: 4 classrooms in use
- Tuesday: 3 classrooms in use (lab day)
- Wednesday: 4 classrooms in use

---

### 8. **System Summary Panel (Right)**
Quick reference box showing:
- 👥 Total Students in system
- 👔 Total Staff
- 🏫 Total Classrooms
- 📋 Today's Sessions

---

## 🕵️ How to Monitor

### Quick Check (2 minutes)
1. Look at top for red/yellow alerts
2. Scan classroom status cards for any 🔴 indicators
3. Check temperature readings

### Detailed Review (5 minutes)
1. Read alert section fully (red/yellow banners)
2. Review each classroom card individually:
   - Is occupancy reasonable?
   - Are expected systems on/off?
   - Is temperature in range?
3. Check key metrics for trends

### Deep Analysis (10 minutes)
1. Study hourly activity chart
   - When is facility busiest?
   - Any unusual patterns?
2. Review weekly trends
   - Are Mondays always busy?
   - Are weekends empty?
3. Check classroom usage comparison
   - Which rooms are most utilized?
   - Which need more scheduling?

---

## 🎯 Common Scenarios

### ⚠️ Red Alert Appears
1. **Read the alert message** - It tells you exactly what's wrong
2. **Identify affected classrooms** - Names listed in the alert
3. **Take action:**
   - Danger flag: Check HVAC, equipment, safety systems
   - Visit the classroom or contact staff
   - When fixed, the alert will disappear automatically

### 🌡️ Temperature Warning
1. **Note the classroom and temperature**
2. **Check if HVAC is running** (should be on in system)
3. **Adjust thermostat** or contact maintenance
4. **Monitor** - Check back in 30 minutes

### 📈 Peak Hours Identified
1. **Note the peak time** (e.g., "10:00-11:00")
2. **Plan for busier times:**
   - Schedule maintenance during off-peak hours
   - Ensure staff coverage during peaks
   - Monitor HVAC more closely during busy times

### 🏫 Classroom Overbooked
1. **See high occupancy percentage** (>90%)
2. **Check occupancy card** - See exact numbers
3. **Consider:**
   - Splitting classes between rooms
   - Staggering schedules
   - Adding more sessions

---

## 🔄 Auto-Refresh

The dashboard updates to show latest data. Charts include:
- Visual smooth animations
- Tooltips on hover (hover over chart points for details)
- Color-coded by importance

---

## 🖥️ Mobile & Tablet

On smaller screens:
- Cards stack vertically
- Alerts remain at top
- Charts still interactive
- All functionality preserved

---

## 🚀 Tips & Tricks

### Pro Tips
1. **Set alerts to auto-refresh** - This can be enabled in future updates
2. **Color-code your thinking** - Red=danger, Yellow=caution, Green=good
3. **Track patterns** - Use weekly charts to spot trends
4. **Peak time planning** - Schedule preventive maintenance during quiet hours
5. **Compare days** - Use charts to see if Monday is always busier

### Quick Decisions
- **Room congestion?** → Look at occupancy cards
- **HVAC issues?** → Check temperature cards
- **Equipment problems?** → Check lights/projector status
- **Overall facility usage?** → Check weekly charts
- **What time to do maintenance?** → Look at hourly activity chart

---

## ⚙️ Settings & Customization

Future enhancements (may be added):
- Email alerts for danger conditions
- Custom time range filtering
- Export reports to PDF
- Mobile app for on-the-go monitoring
- Predictive alerts before problems happen

---

## 📊 Understanding the Data

### Occupancy Percentage
```
33% = 1/3 of rooms filled
67% = 2/3 of rooms filled
100% = All seats taken

🟢 Low: <50% (comfortable)
🟡 Medium: 50-80% (getting busy)
🔴 High: >80% (very crowded)
```

### Session Count
One "session" = One recorded attendance entry
- If 25 students enter simultaneously = 1 session
- If 25 students enter over 5 hours = multiple sessions
- Higher = More classroom activity

### Temperature Range
```
🟢 Ideal: 18-22°C (comfortable)
🟡 Acceptable: 15-28°C (within range)
🔴 Warning: <15°C or >28°C (too cold/hot)
```

---

## 🆘 If Something Looks Wrong

| Symptom | Likely Issue | Action |
|---------|-------------|--------|
| Red danger alert | Critical issue | Read alert, investigate immediately |
| High temperature | HVAC failure | Check system, call maintenance |
| Equipment shows OFF | Not in use | Check if session is over |
| 0% occupancy | Room empty | Normal if not scheduled |
| All data missing | System issue | Contact IT support |

---

## 📞 Quick Reference

**Dashboard URL:** `http://localhost:8000/` or `http://[server]/`

**What to Monitor:**
- ✅ Alerts Section (Red/Yellow/Green at top)
- ✅ Classroom Status Cards (Current state)
- ✅ Key Metrics (Average occupancy, peak hours)
- ✅ Charts (Trends and patterns)

**When to Act:**
- 🔴 Red alert = IMMEDIATE
- 🟡 Yellow alert = Within 1 hour
- 🟢 Green = Monitor normally

---

**Dashboard is production-ready and requires no changes!**
Use it daily for comprehensive classroom supervision.
