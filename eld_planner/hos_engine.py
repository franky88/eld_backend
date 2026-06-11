from datetime import date, timedelta


# ── HOS Constants ────────────────────────────────────────────────────────────
MAX_DRIVE_PER_WINDOW   = 11.0   # hours
MAX_WINDOW             = 14.0   # consecutive hours from shift start
OFF_DUTY_REQUIRED      = 10.0   # consecutive hours off before next window
BREAK_AFTER            = 8.0    # cumulative driving hours before mandatory break
BREAK_DURATION         = 0.5    # 30 minutes
MAX_CYCLE              = 70.0   # hours / 8 days
FUEL_INTERVAL          = 1000.0 # miles
PICKUP_DROPOFF_TIME    = 1.0    # hour on-duty not driving
PRETRIP_TIME           = 0.5    # hour on-duty not driving
FUEL_STOP_TIME         = 0.5    # hour on-duty not driving
SHIFT_START            = 6.0    # 6:00 AM


def _fmt_time(hour: float) -> str:
    """Convert decimal hour to HH:MM string."""
    h = int(hour) % 24
    m = int(round((hour - int(hour)) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def plan_trip(
    total_miles: float,
    avg_speed_mph: float,
    stops: list,          # [{"type": "pickup"|"dropoff"|"fuel", "miles": float, "label": str}]
    cycle_used: float,
    start_date: date = None,
    home_terminal: str = 'N/A',
    carrier: str = 'N/A',
    main_office: str = 'N/A',
    tractor_number: str = 'N/A',
    trailer_number: str = 'N/A',
    driver_signature: str = 'Driver',
) -> list:
    """
    Core HOS engine. Returns a list of DayPlan dicts.

    Each DayPlan:
      {
        "day": int,
        "fields": { date, total_miles, carrier, ... },
        "events": [ { status, start_hour, end_hour, is_stationary } ],
        "remarks": [ { time, location, activity } ],
        "totals": { offDuty, sleeperBerth, driving, onDutyNotDriving }
      }
    """
    if start_date is None:
        start_date = date.today()

    days = []
    miles_driven = 0.0
    cycle_hrs = cycle_used
    day_number = 0

    # Sort stops by mileage
    stops_sorted = sorted(stops, key=lambda s: s['miles'])
    stop_index = 0  # next unvisited stop
    last_location = stops_sorted[0]['label'] if stops_sorted else 'Origin'

    # Track fuel: last fuel stop mileage
    last_fuel_miles = 0.0

    while miles_driven < total_miles:
        day_number += 1
        current_date = start_date + timedelta(days=day_number - 1)

        events = []
        remarks = []
        day_miles = 0.0

        clock = SHIFT_START          # current clock time this day (decimal hours)
        cumul_drive = 0.0            # driving hours this window
        since_break = 0.0            # driving hours since last 30-min break
        window_start = SHIFT_START   # when this 14-hr window started
        took_break = False

        # ── Off duty block before shift (midnight to shift start) ───────────
        if SHIFT_START > 0:
            events.append({
                'status': 'offDuty',
                'start_hour': 0.0,
                'end_hour': SHIFT_START,
                'is_stationary': False,
            })

        # ── Pre-trip inspection ──────────────────────────────────────────────
        events.append({
            'status': 'onDutyNotDriving',
            'start_hour': clock,
            'end_hour': clock + PRETRIP_TIME,
            'is_stationary': True,
        })
        remarks.append({
            'time': _fmt_time(clock),
            'location': last_location,
            'activity': 'On duty / pre-trip inspection',
        })
        cycle_hrs += PRETRIP_TIME
        clock += PRETRIP_TIME

        # ── Main driving loop for this day ───────────────────────────────────
        while miles_driven < total_miles:
            window_elapsed = clock - window_start
            drive_remaining_window = min(
                MAX_DRIVE_PER_WINDOW - cumul_drive,
                MAX_WINDOW - window_elapsed,
            )

            # Check 14-hr window or 11-hr drive limit exhausted
            if drive_remaining_window <= 0:
                break

            # Check cycle limit
            cycle_remaining = MAX_CYCLE - cycle_hrs
            if cycle_remaining <= 0:
                break

            # Check if 30-min break needed before driving
            if since_break >= BREAK_AFTER and not took_break:
                events.append({
                    'status': 'offDuty',
                    'start_hour': clock,
                    'end_hour': clock + BREAK_DURATION,
                    'is_stationary': False,
                })
                remarks.append({
                    'time': _fmt_time(clock),
                    'location': last_location,
                    'activity': '30-min rest break',
                })
                clock += BREAK_DURATION
                took_break = True
                since_break = 0.0
                continue

            # ── Find the next event (stop or limit) ─────────────────────────
            # How far can we drive before hitting a limit?
            max_drive_hrs = min(
                drive_remaining_window,
                cycle_remaining,
                BREAK_AFTER - since_break if not took_break else drive_remaining_window,
            )
            max_drive_miles = max_drive_hrs * avg_speed_mph

            # Find next stop within range
            next_stop = None
            if stop_index < len(stops_sorted):
                s = stops_sorted[stop_index]
                miles_to_stop = s['miles'] - miles_driven
                if miles_to_stop <= max_drive_miles and miles_to_stop >= 0:
                    next_stop = s

            # Check fuel stop
            next_fuel_miles = last_fuel_miles + FUEL_INTERVAL
            miles_to_fuel = next_fuel_miles - miles_driven
            needs_fuel = (
                miles_to_fuel <= max_drive_miles
                and miles_to_fuel > 0
                and not any(
                    abs(s['miles'] - next_fuel_miles) < 50
                    for s in stops_sorted
                )
            )

            # Determine how far to drive this segment
            if next_stop is not None:
                drive_miles = max(0, stops_sorted[stop_index]['miles'] - miles_driven)
            elif needs_fuel:
                drive_miles = miles_to_fuel
            else:
                drive_miles = min(max_drive_miles, total_miles - miles_driven)

            drive_miles = min(drive_miles, total_miles - miles_driven)

            if drive_miles <= 0 and next_stop is None:
                break

            # ── Drive segment ────────────────────────────────────────────────
            if drive_miles > 0:
                drive_hrs = drive_miles / avg_speed_mph
                events.append({
                    'status': 'driving',
                    'start_hour': clock,
                    'end_hour': clock + drive_hrs,
                    'is_stationary': False,
                })
                remarks.append({
                    'time': _fmt_time(clock),
                    'location': last_location,
                    'activity': 'Driving',
                })
                clock += drive_hrs
                cumul_drive += drive_hrs
                since_break += drive_hrs
                cycle_hrs += drive_hrs
                miles_driven += drive_miles
                day_miles += drive_miles

            # ── Handle stop ──────────────────────────────────────────────────
            if next_stop is not None and miles_driven >= stops_sorted[stop_index]['miles'] - 0.01:
                s = stops_sorted[stop_index]
                last_location = s['label']

                if s['type'] == 'fuel':
                    events.append({
                        'status': 'onDutyNotDriving',
                        'start_hour': clock,
                        'end_hour': clock + FUEL_STOP_TIME,
                        'is_stationary': True,
                    })
                    remarks.append({
                        'time': _fmt_time(clock),
                        'location': last_location,
                        'activity': 'Fuel stop — 30 min',
                    })
                    cycle_hrs += FUEL_STOP_TIME
                    clock += FUEL_STOP_TIME
                    last_fuel_miles = miles_driven

                elif s['type'] in ('pickup', 'dropoff'):
                    label = 'Pickup' if s['type'] == 'pickup' else 'Dropoff'
                    events.append({
                        'status': 'onDutyNotDriving',
                        'start_hour': clock,
                        'end_hour': clock + PICKUP_DROPOFF_TIME,
                        'is_stationary': True,
                    })
                    remarks.append({
                        'time': _fmt_time(clock),
                        'location': last_location,
                        'activity': f'{label} — 1 hr on duty',
                    })
                    cycle_hrs += PICKUP_DROPOFF_TIME
                    clock += PICKUP_DROPOFF_TIME

                stop_index += 1

            elif needs_fuel and drive_miles == miles_to_fuel:
                # Unplanned fuel stop
                fuel_label = f'Mile {int(miles_driven)} Fuel Stop'
                last_location = fuel_label
                events.append({
                    'status': 'onDutyNotDriving',
                    'start_hour': clock,
                    'end_hour': clock + FUEL_STOP_TIME,
                    'is_stationary': True,
                })
                remarks.append({
                    'time': _fmt_time(clock),
                    'location': fuel_label,
                    'activity': 'Fuel stop — 30 min',
                })
                cycle_hrs += FUEL_STOP_TIME
                clock += FUEL_STOP_TIME
                last_fuel_miles = miles_driven

        # ── End of driving day: 10-hr off duty ──────────────────────────────
        if miles_driven < total_miles:
            off_start = clock
            off_end = min(off_start + OFF_DUTY_REQUIRED, 24.0)
            events.append({
                'status': 'offDuty',
                'start_hour': off_start,
                'end_hour': off_end,
                'is_stationary': False,
            })
            remarks.append({
                'time': _fmt_time(off_start),
                'location': last_location,
                'activity': '10-hr off duty — required rest',
            })
            # Fill remainder of 24 hrs if needed
            if off_end < 24.0:
                events.append({
                    'status': 'offDuty',
                    'start_hour': off_end,
                    'end_hour': 24.0,
                    'is_stationary': False,
                })
        else:
            # Trip complete — post-trip and off duty rest
            events.append({
                'status': 'onDutyNotDriving',
                'start_hour': clock,
                'end_hour': clock + PRETRIP_TIME,
                'is_stationary': True,
            })
            remarks.append({
                'time': _fmt_time(clock),
                'location': last_location,
                'activity': 'Post-trip inspection',
            })
            cycle_hrs += PRETRIP_TIME
            clock += PRETRIP_TIME

            if clock < 24.0:
                events.append({
                    'status': 'offDuty',
                    'start_hour': clock,
                    'end_hour': 24.0,
                    'is_stationary': False,
                })

        # ── Merge consecutive same-status events ─────────────────────────────
        events = _merge_events(events)

        # ── Calculate totals ─────────────────────────────────────────────────
        totals = _calc_totals(events)

        days.append({
            'day': day_number,
            'fields': {
                'date': current_date.isoformat(),
                'total_miles': round(day_miles, 1),
                'carrier': carrier,
                'tractor_number': tractor_number,
                'trailer_number': trailer_number,
                'main_office': main_office,
                'home_terminal': home_terminal,
                'driver_signature': driver_signature,
            },
            'events': events,
            'remarks': remarks,
            'totals': totals,
        })

    return days


def _merge_events(events: list) -> list:
    """Merge back-to-back events with the same status and is_stationary=False."""
    if not events:
        return events
    merged = [events[0].copy()]
    for ev in events[1:]:
        last = merged[-1]
        if (ev['status'] == last['status']
                and not ev['is_stationary']
                and not last['is_stationary']
                and abs(ev['start_hour'] - last['end_hour']) < 0.001):
            last['end_hour'] = ev['end_hour']
        else:
            merged.append(ev.copy())
    return merged


def _calc_totals(events: list) -> dict:
    """Sum hours per status row. Pad offDuty to ensure total == 24.0."""
    totals = {'offDuty': 0.0, 'sleeperBerth': 0.0, 'driving': 0.0, 'onDutyNotDriving': 0.0}
    for ev in events:
        totals[ev['status']] += ev['end_hour'] - ev['start_hour']

    # Ensure sum is exactly 24.0
    total_sum = sum(totals.values())
    diff = 24.0 - total_sum
    if abs(diff) > 0.001:
        totals['offDuty'] = round(totals['offDuty'] + diff, 4)

    return {k: round(v, 2) for k, v in totals.items()}