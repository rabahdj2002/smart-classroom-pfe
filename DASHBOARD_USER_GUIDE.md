# HeisenHelmet Safety Cloud - Administrator Guide

## 🏠 Dashboard Overview

Your HeisenHelmet dashboard is a centralized command center for monitoring the safety of your fleet. 

---

## 🛡️ Safety Status System

Helmets automatically report their status based on complex onboard sensor logic and background verification.

*   **🟢 Online**: The helmet is connected and transmitting data normally.
*   **⚪ Offline**: No heartbeat received for over 60 seconds (device may be powered off or out of range).
*   **🟡 Drunk**: Alcohol sensor detected levels exceeding your configured threshold. **Action Required.**
*   **🔴 Accident**: Impact or crash detected. This status remains until the incident is manually resolved in the "Incidents" tab.

---

## ⚙️ Platform Configuration (Settings)

As an administrator, you can globally control the behavior of all helmets from the **Settings** menu.

### Safety Thresholds
*   **Max Allowed Alcohol**: Define the mg/L limit. If a rider exceeds this, an Incident is automatically logged.
*   **Speed Limit**: Sets the global speed limit (km/h) sent to all devices for local enforcement/audits.
*   **Inactivity Timeout**: How many minutes a rider can stay stationary before being flagged as idle.

### MQTT & Hosting Infrastructure
If you are hosting this on your own server with a domain (e.g., via Cloudflare):
1.  **Public WebSocket Host**: Enter your subdomain (e.g., `mqtt.yourdomain.com`). This ensures the live map works in your browser.
2.  **Enable WSS (SSL)**: Keep this enabled if your site is https (Cloudflare Standard).
3.  **Broker Port**: Usually `443` for Cloudflare tunnels or `8883` for direct SSL.

---

## 🚨 Incident Management

When a critical event (Crash or Alcohol Trigger) occurs:
1.  **Global Alert**: A notification badge appears in the sidebar next to "Incidents".
2.  **Incident Log**: Detailed GPS coordinates, timestamp, and rider info are recorded.
3.  **Resolution**: Click "Resolve Incident" after verifying the rider's safety. This will restore the helmet status from **Accident** back to **Online**.

---

## 🗺️ Live Tracking Map

The real-time map uses the **Map Refresh Rate** set in your settings. 
- **Green Icons**: Safe riders.
- **Red Pulsing Icons**: Active incidents.
- **Path History**: Click any rider to view their breadcrumb trail for the current active route.
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
