from pathlib import Path

REF = Path("src/icon_v15_reference_generated.pine")
OUT = Path("src/icon_bot_frozen_option2a.pine")

if not REF.exists():
    raise SystemExit(f"Missing {REF}. Run: python src/build_icon_pine.py")

v15 = REF.read_text()

HEADER = r'''//@version=6
strategy("Icon Bot", "Icon Bot", overlay = true, pyramiding = 0, process_orders_on_close = false, calc_on_order_fills = false, calc_on_every_tick = true, use_bar_magnifier = true, default_qty_type = strategy.fixed, initial_capital = 1000000, margin_long = 1, margin_short = 1, max_lines_count = 500, max_labels_count = 500, max_boxes_count = 500, max_bars_back = 5000)

// THE ICON — FROZEN OPTION 2A
// Strategy engine only is replaced. Existing session/visual/risk/PMT settings retained.
// 3-minute chart only.

disp = display.all - display.status_line

// ─────────────────────────────────────────────────────────────────────────────
// INPUTS
// ─────────────────────────────────────────────────────────────────────────────
logoGR = "0. Logo"
logoTextSizeStr = input.string("Normal", "Text Size", options = ["Tiny", "Small", "Normal", "Large", "Huge"], group = logoGR)
logoTextColor = input.color(#4F5F4E, "Text Color", group = logoGR)
logoBorderColor = input.color(#6B7F6A, "Border Color", group = logoGR)
logoBgColor = input.color(#6B7F6A, "Background Tint", group = logoGR)
logoTextSize = logoTextSizeStr == "Tiny" ? size.tiny : logoTextSizeStr == "Small" ? size.small : logoTextSizeStr == "Large" ? size.large : logoTextSizeStr == "Huge" ? size.huge : size.normal
logoTable = table.new(position.bottom_center, 1, 1, bgcolor = color.new(logoBgColor, 92), frame_color = color.new(logoBorderColor, 30), frame_width = 1)
if barstate.islast
    table.cell(logoTable, 0, 0, "        THE ⚡ CON BOT        ", text_color = logoTextColor, text_size = logoTextSize, bgcolor = color.new(logoBgColor, 92))

dashGR = "0b. Dashboard"
dashShow = input.bool(true, "Show Dashboard", group = dashGR)
dashPos = position.top_right
dashTextSize = size.normal
dashBgColor = #6B7F6A
dashBgTransp = 93
dashBorderColor = #6B7F6A
dashBorderTransp = 30
dashLabelColor = #8A7A5C
dashValueColor = #2B2620
dashPositiveColor = #4F5F4E
dashNegativeColor = #9E7A6E

kzGR = "1. Killzones — Minimal Glass"
kzTZ = input.string("America/New_York", "Session Timezone", group = kzGR, tooltip = "Uses New York time and automatically handles EST/EDT daylight-saving changes.", display = disp)
asSH = input.bool(true, "Asia", inline = "asia", group = kzGR)
asCol = input.color(#A78855, "Color", inline = "asia", group = kzGR)
asS = input.session("2000-0000", "Asia session", group = kzGR)
ldnOSH = input.bool(true, "London", inline = "london", group = kzGR)
ldnOCol = input.color(#A78855, "Color", inline = "london", group = kzGR)
ldnOS = input.session("0200-0500", "London session", group = kzGR)
nySH = input.bool(true, "NY AM", inline = "nyam", group = kzGR)
nyCol = input.color(#A78855, "Color", inline = "nyam", group = kzGR)
nyS = input.session("0930-1230", "NY AM session", group = kzGR)
ldnCSH = input.bool(true, "NY PM", inline = "nypm", group = kzGR)
ldnCCol = input.color(#A78855, "Color", inline = "nypm", group = kzGR)
ldnCS = input.session("1330-1700", "NY PM session", group = kzGR)
kzKeepSessions = input.int(60, "Keep Last N Killzone Boxes", minval = 4, maxval = 400, group = kzGR, display = disp)

riskGR = "4. Risk / Reward + Sizing"
slATRLen = input.int(14, "ATR Length", minval = 1, group = riskGR, display = disp)
rrRatio = input.float(3.0, "Risk / Reward Ratio", minval = 0.1, step = 0.1, group = riskGR, display = disp)
riskPerTrade = input.float(250.0, "Risk per Trade ($)", minval = 0.0, step = 1.0, group = riskGR, display = disp)
qtyDec = input.int(0, "Quantity Decimals", minval = 0, maxval = 4, group = riskGR, display = disp)
rrSH = input.bool(true, "Show Risk / Reward Visuals", group = riskGR)
rrKeep = input.int(30, "Keep Visuals For Last N Trades", minval = 1, maxval = 60, group = riskGR, display = disp)
rrRiskC = input.color(color.new(#5B080F, 90), "Risk Area", inline = "RRC", group = riskGR)
rrRewardC = input.color(color.new(#022404, 90), "Reward Area", inline = "RRC", group = riskGR)
rrEntryC = input.color(color.new(#000000, 85), "Entry", inline = "RRL", group = riskGR)
rrStopC = input.color(color.new(#5B080F, 85), "Stop", inline = "RRL", group = riskGR)
rrTargetC = input.color(color.new(#022404, 85), "Target", inline = "RRL", group = riskGR)

lblGR = "5. Trade Labels"
lblSH = input.bool(true, "Show Entry + Exit Labels", group = lblGR)
lblSize = input.string("Small", "Label Size", options = ["Tiny", "Small", "Normal"], group = lblGR, display = disp)
lblOffsetATR = input.float(2.0, "Label Distance From Candle (x ATR)", minval = 0.2, step = 0.1, group = lblGR, display = disp)
teLblSize = lblSize == "Tiny" ? size.tiny : lblSize == "Normal" ? size.normal : size.small
col_bullish = #6B7F6A
col_bearish = #9E7A6E

pmtGR = "7. PickMyTrade Automation"
pmtEnabled = input.bool(false, "Enable PickMyTrade Order-Fill Alerts", group = pmtGR)
pmtSymbol = input.string("MNQ1!", "PickMyTrade Symbol", group = pmtGR)
pmtStrategyName = input.string("Icon Bot Demo", "PickMyTrade Strategy Name", group = pmtGR)
pmtToken = input.string("", "PickMyTrade Token", group = pmtGR)
pmtAccountId = input.string("", "PickMyTrade Account ID", group = pmtGR)
pmtQtyMultiplier = input.float(1.0, "Quantity Multiplier", minval = 0.0, step = 0.1, group = pmtGR)

type TradeVis
    box bxRisk = na
    box bxReward = na
    line lnEntry = na
    line lnStop = na
    line lnTarget = na
    label lbEntry = na

f_qty(float stopDist) =>
    pv = nz(syminfo.pointvalue, 1.0)
    raw = stopDist * pv > 0 ? riskPerTrade / (stopDist * pv) : 0.0
    factor = math.pow(10.0, qtyDec)
    math.floor(raw * factor) / factor

f_jsonNum(float x) => str.tostring(x, format.mintick)

f_pmtEntryPayload(string action, float qty, float entry, float sl, float tp) =>
    string msg = "{\"symbol\":\"" + pmtSymbol + "\""
    msg += ",\"strategy_name\":\"" + pmtStrategyName + "\""
    msg += ",\"date\":\"" + str.tostring(timenow) + "\""
    msg += ",\"data\":\"" + action + "\""
    msg += ",\"quantity\":" + str.tostring(qty)
    msg += ",\"risk_percentage\":0"
    msg += ",\"price\":" + f_jsonNum(entry)
    msg += ",\"tp\":" + f_jsonNum(tp)
    msg += ",\"percentage_tp\":0,\"dollar_tp\":0"
    msg += ",\"sl\":" + f_jsonNum(sl)
    msg += ",\"dollar_sl\":0,\"percentage_sl\":0"
    msg += ",\"trail\":0,\"trail_stop\":0,\"trail_trigger\":0,\"trail_freq\":0"
    msg += ",\"update_tp\":false,\"update_sl\":false,\"breakeven\":0,\"breakeven_offset\":0"
    msg += ",\"token\":\"" + pmtToken + "\""
    msg += ",\"pyramid\":false,\"same_direction_ignore\":false,\"reverse_order_close\":false"
    msg += ",\"multiple_accounts\":[{\"token\":\"" + pmtToken + "\",\"account_id\":\"" + pmtAccountId + "\",\"risk_percentage\":0,\"quantity_multiplier\":" + str.tostring(pmtQtyMultiplier) + "}]}"
    msg

f_pmtClosePayload() =>
    string msg = "{\"symbol\":\"" + pmtSymbol + "\""
    msg += ",\"strategy_name\":\"" + pmtStrategyName + "\""
    msg += ",\"date\":\"" + str.tostring(timenow) + "\""
    msg += ",\"data\":\"CLOSE\",\"quantity\":0,\"risk_percentage\":0"
    msg += ",\"price\":" + f_jsonNum(close)
    msg += ",\"tp\":0,\"percentage_tp\":0,\"dollar_tp\":0,\"sl\":0,\"dollar_sl\":0,\"percentage_sl\":0"
    msg += ",\"trail\":0,\"trail_stop\":0,\"trail_trigger\":0,\"trail_freq\":0"
    msg += ",\"update_tp\":false,\"update_sl\":false,\"breakeven\":0,\"breakeven_offset\":0"
    msg += ",\"token\":\"" + pmtToken + "\",\"pyramid\":false,\"same_direction_ignore\":false,\"reverse_order_close\":false"
    msg += ",\"multiple_accounts\":[{\"token\":\"" + pmtToken + "\",\"account_id\":\"" + pmtAccountId + "\",\"risk_percentage\":0,\"quantity_multiplier\":" + str.tostring(pmtQtyMultiplier) + "}]}"
    msg

// ─────────────────────────────────────────────────────────────────────────────
// SESSIONS + GLASS BOXES
// ─────────────────────────────────────────────────────────────────────────────
isIntra = timeframe.isintraday
inAsia = isIntra and asSH and not na(time(timeframe.period, asS, kzTZ))
inLdnO = isIntra and ldnOSH and not na(time(timeframe.period, ldnOS, kzTZ))
inNyAm = isIntra and nySH and not na(time(timeframe.period, nyS, kzTZ))
inNyPm = isIntra and ldnCSH and not na(time(timeframe.period, ldnCS, kzTZ))
inKZ = inAsia or inLdnO or inNyAm or inNyPm
sessName = inNyAm ? "NYAM" : inNyPm ? "NYPM" : inLdnO ? "LONDON" : inAsia ? "ASIA" : "NONE"
sessChanged = sessName != sessName[1]
sessStarted = sessChanged and sessName != "NONE"

var box[] kzBoxes = array.new_box(4, na)
var label[] kzLabels = array.new_label(4, na)
var box[] kzBoxHistory = array.new_box(0)
var label[] kzLabelHistory = array.new_label(0)
kzNames = array.from("ASIA", "LONDON", "NY AM", "NY PM")
kzCols = array.from(asCol, ldnOCol, nyCol, ldnCCol)
kzShows = array.from(asSH, ldnOSH, nySH, ldnCSH)
f_kzIndex(string nm) => nm == "ASIA" ? 0 : nm == "LONDON" ? 1 : nm == "NYAM" ? 2 : nm == "NYPM" ? 3 : -1

if isIntra
    if sessStarted
        kzIdx = f_kzIndex(sessName)
        if kzIdx >= 0 and array.get(kzShows, kzIdx)
            kcol = array.get(kzCols, kzIdx)
            nm = array.get(kzNames, kzIdx)
            b = box.new(bar_index, high, bar_index, low, border_color = color.new(kcol, 30), border_width = 1, bgcolor = color.new(kcol, 92), extend = extend.none)
            l = label.new(bar_index, high, nm, style = label.style_label_down, color = color.new(color.black, 100), textcolor = kcol, size = size.small)
            array.set(kzBoxes, kzIdx, b)
            array.set(kzLabels, kzIdx, l)
            array.push(kzBoxHistory, b)
            array.push(kzLabelHistory, l)
            if array.size(kzBoxHistory) > kzKeepSessions
                oldB = array.shift(kzBoxHistory)
                oldL = array.shift(kzLabelHistory)
                if not na(oldB)
                    box.delete(oldB)
                if not na(oldL)
                    label.delete(oldL)
    if inKZ
        kzIdxNow = f_kzIndex(sessName)
        if kzIdxNow >= 0
            b = array.get(kzBoxes, kzIdxNow)
            l = array.get(kzLabels, kzIdxNow)
            if not na(b)
                box.set_right(b, bar_index)
                box.set_top(b, math.max(box.get_top(b), high))
                box.set_bottom(b, math.min(box.get_bottom(b), low))
                if not na(l)
                    label.set_x(l, box.get_left(b))
                    label.set_y(l, box.get_top(b))

barcolor(close >= open ? col_bullish : col_bearish, editable = false)
atrForStop = ta.atr(slATRLen)

// Frozen thresholds
V15_SCORE_THRESHOLD = 0.145921011058
V27_RTH = 0.576132
V27_WTH = 0.183258
MAX_V15_PER_ET_DAY = 6

// Exact 3m ATR(20), same as Python candidate engine.
tr3 = math.max(high - low, math.max(math.abs(high - close[1]), math.abs(low - close[1])))
atr3 = ta.sma(tr3, 20)

// 1m causal features. These expressions are calculated in 1m context, then returned
// as arrays for the three constituent minutes of each 3m bar.
[o1, h1, l1, c1, a1, d1, bull6, bear6] = request.security_lower_tf(syminfo.tickerid, "1", [
    open,
    high,
    low,
    close,
    ta.sma(math.max(high-low, math.max(math.abs(high-close[1]), math.abs(low-close[1]))), 20),
    close-open,
    (close > open ? 1 : 0) + (close[1] > open[1] ? 1 : 0) + (close[2] > open[2] ? 1 : 0) + (close[3] > open[3] ? 1 : 0) + (close[4] > open[4] ? 1 : 0) + (close[5] > open[5] ? 1 : 0),
    (close < open ? 1 : 0) + (close[1] < open[1] ? 1 : 0) + (close[2] < open[2] ? 1 : 0) + (close[3] < open[3] ? 1 : 0) + (close[4] < open[4] ? 1 : 0) + (close[5] < open[5] ? 1 : 0)
])
'''

ENGINE = r'''

f_v15_score(float rejection_quality, float impulse_to_reclaim, float reclaim_to_sweep,
    float reversal_impulse, float reclaim_x_wick, float close_x_reclaim,
    float sweep_minus_reclaim, float impulse_minus_reclaim, float quality_balance) =>
    p0 = f_frozen_pct_rank(rejection_quality, v15_0_values, v15_0_counts, 1477)
    p1 = f_frozen_pct_rank(impulse_to_reclaim, v15_1_values, v15_1_counts, 1477)
    p2 = f_frozen_pct_rank(reclaim_to_sweep, v15_2_values, v15_2_counts, 1477)
    p3 = f_frozen_pct_rank(reversal_impulse, v15_3_values, v15_3_counts, 1477)
    p4 = f_frozen_pct_rank(reclaim_x_wick, v15_4_values, v15_4_counts, 1477)
    p5 = f_frozen_pct_rank(close_x_reclaim, v15_5_values, v15_5_counts, 1477)
    p6 = f_frozen_pct_rank(sweep_minus_reclaim, v15_6_values, v15_6_counts, 1477)
    p7 = f_frozen_pct_rank(impulse_minus_reclaim, v15_7_values, v15_7_counts, 1477)
    p8 = f_frozen_pct_rank(quality_balance, v15_8_values, v15_8_counts, 1477)
    (2*p0 + 2*p1 + (1-p2) + p3 + 2*(1-p4) + 2*(1-p5) + p6 + 2*p7 + 2*p8) / 15.0

var int v15CountToday = 0
var float runHi = na
var float runLo = na
var float pendingStop = na
var bool pendingLong = false
var string pendingSess = "NONE"
var bool orderPending = false

var int startedTrades = 0
var int processedClosedTrades = 0
var float stEntry = na
var float stStop = na
var float stTarget = na
var float stQty = na
var bool stBull = false
var string stSessName = "NONE"
var TradeVis stVis = na
var array<TradeVis> visHist = array.new<TradeVis>(0)

var int dayTrades = 0
var int dayLosses = 0
var int dayWins = 0
var float dayPnL = 0.0
var float pnlAsia = 0.0
var float pnlLondon = 0.0
var float pnlNYAM = 0.0
var float pnlNYPM = 0.0

f_eval_candidate(int v15N, float hiRun, float loRun, float pStop, bool pLong, string pSess, bool pOrder) =>
    int v15CountTodayL = v15N
    float runHiL = hiRun
    float runLoL = loRun
    float pendingStopL = pStop
    bool pendingLongL = pLong
    string pendingSessL = pSess
    bool orderPendingL = pOrder
    if inKZ and not sessStarted and barstate.isconfirmed and not na(runHiL) and not na(runLoL)
        bool newLow = low < runLoL
        bool newHigh = high > runHiL
        int n1 = array.size(c1)
        bool have3 = n1 >= 3 and array.size(o1) >= 3 and array.size(h1) >= 3 and array.size(l1) >= 3 and array.size(a1) >= 3

        if have3 and (newLow or newHigh)
            for side = 0 to 1
                bool isLong = side == 0
                bool exists = isLong ? newLow : newHigh
                if exists
                    float sg = isLong ? 1.0 : -1.0
                    float extreme = isLong ? low : high
                    float sweepDistance = isLong ? (runLoL - low) : (high - runHiL)
                    float rng = high - low
                    float wickPercent = rng > 0 ? (isLong ? (math.min(open, close)-low)/rng : (high-math.max(open, close))/rng) : 0.0

                    float baseClose = array.get(c1, 0)
                    float a = array.get(a1, 0)
                    float m1h = array.get(h1, 1)
                    float m1l = array.get(l1, 1)
                    float m1c = array.get(c1, 1)
                    float m2h = array.get(h1, 2)
                    float m2l = array.get(l1, 2)
                    float m2c = array.get(c1, 2)

                    if not na(a) and a > 0 and not na(atr3) and atr3 > 0
                        float m1Move = (m1c - baseClose) / a * sg
                        float m1cp = m1h > m1l ? (m1c - m1l) / (m1h - m1l) : 0.5
                        float m1ClosePos = isLong ? m1cp : 1.0 - m1cp
                        float m2Move = (m2c - baseClose) / a * sg
                        float m2cp = m2h > m2l ? (m2c - m2l) / (m2h - m2l) : 0.5
                        float m2ClosePos = isLong ? m2cp : 1.0 - m2cp
                        float reclaim = isLong ? (m2c - extreme) / a : (extreme - m2c) / a

                        int m2DirBars5 = int(array.get(isLong ? bull6 : bear6, 2))
                        if not isLong
                            m2DirBars5 := 6 - m2DirBars5

                        bool v7 = m1Move <= 0.300 and m1ClosePos >= 0.140 and m2ClosePos <= 0.912
                        bool v8 = reclaim <= 0.90 and m2ClosePos <= 0.80 and wickPercent <= 0.60 and m2Move <= 0.15 and m2DirBars5 <= 4

                        if v7 and v8
                            float sweepAtr = sweepDistance / atr3
                            float rejectionQuality = (1 - math.min(math.max(m2ClosePos, 0), 1)) * (1 - math.min(math.max(wickPercent, 0), 1))
                            float reversalImpulse = -m2Move
                            float reclaimToSweep = reclaim / (math.abs(sweepAtr) + 0.05)
                            float impulseToReclaim = reversalImpulse / (math.abs(reclaim) + 0.05)
                            float reclaimXWick = reclaim * wickPercent
                            float closeXReclaim = m2ClosePos * reclaim
                            float sweepMinusReclaim = sweepAtr - reclaim
                            float impulseMinusReclaim = reversalImpulse - reclaim
                            float qualityBalance = rejectionQuality * impulseToReclaim / (1 + reclaimToSweep)
                            float score = f_v15_score(rejectionQuality, impulseToReclaim, reclaimToSweep, reversalImpulse, reclaimXWick, closeXReclaim, sweepMinusReclaim, impulseMinusReclaim, qualityBalance)

                            bool v15 = score >= V15_SCORE_THRESHOLD
                            if v15 and v15CountTodayL < MAX_V15_PER_ET_DAY
                                v15CountTodayL += 1
                                bool v27 = not (reclaim >= V27_RTH and reclaimXWick >= V27_WTH)
                                if v27 and strategy.position_size == 0 and not orderPendingL
                                    pendingStopL := isLong ? extreme - 0.25 : extreme + 0.25
                                    pendingLongL := isLong
                                    pendingSessL := sessName
                                    orderPendingL := true
                                    strategy.entry(isLong ? "IB Long" : "IB Short", isLong ? strategy.long : strategy.short, qty = 1)

    if inKZ and not sessStarted
        runHiL := math.max(runHiL, high)
        runLoL := math.min(runLoL, low)
    [v15CountTodayL, runHiL, runLoL, pendingStopL, pendingLongL, pendingSessL, orderPendingL]

f_handle_fill(int startedN, float pStop, bool pLong, string pSess, bool pOrder, TradeVis visIn) =>
    int startedTradesL = startedN
    bool orderPendingL = pOrder
    TradeVis visOut = visIn
    // Declare return-state locals at function scope. Pine block-scopes variables
    // declared inside an if, so these must exist before the newFill branch.
    bool stBullL = pLong
    float stEntryL = na
    float stStopL = pStop
    float stQtyL = na
    float stTargetL = na
    string stSessNameL = pSess
    int currentStartedTrades = strategy.closedtrades + strategy.opentrades
    bool newFill = currentStartedTrades > startedTradesL
    if newFill
        float actualEntry = na
        int actualEntryBar = na
        if strategy.opentrades > 0
            int t = strategy.opentrades - 1
            actualEntry := strategy.opentrades.entry_price(t)
            actualEntryBar := strategy.opentrades.entry_bar_index(t)
        else
            int t = strategy.closedtrades - 1
            actualEntry := strategy.closedtrades.entry_price(t)
            actualEntryBar := strategy.closedtrades.entry_bar_index(t)

        stBullL := pLong
        stEntryL := actualEntry
        stStopL := pStop
        float riskDist = stBullL ? stEntryL - stStopL : stStopL - stEntryL
        stQtyL := f_qty(riskDist)
        stTargetL := stBullL ? stEntryL + riskDist * rrRatio : stEntryL - riskDist * rrRatio
        stSessNameL := pSess
        startedTradesL := currentStartedTrades
        orderPendingL := false

        if riskDist > 0
            string closeMsg = pmtEnabled ? f_pmtClosePayload() : ""
            if stBullL
                strategy.exit("IB Long Exit", "IB Long", stop = stStopL, limit = stTargetL, comment_loss = "SL_HIT", comment_profit = "TP_HIT", alert_loss = closeMsg, alert_profit = closeMsg)
            else
                strategy.exit("IB Short Exit", "IB Short", stop = stStopL, limit = stTargetL, comment_loss = "SL_HIT", comment_profit = "TP_HIT", alert_loss = closeMsg, alert_profit = closeMsg)

            visOut := TradeVis.new()
            if lblSH
                float lblY = stBullL ? stEntryL - atrForStop * lblOffsetATR : stEntryL + atrForStop * lblOffsetATR
                color chipCol = stBullL ? col_bullish : col_bearish
                visOut.lbEntry := label.new(actualEntryBar, lblY, stBullL ? "[ ▲ BUY ]" : "[ ▼ SELL ]", xloc.bar_index, yloc.price, color = color.new(color.black, 100), style = label.style_label_center, textcolor = chipCol, size = teLblSize)
            if rrSH
                float rTop = stBullL ? stEntryL : stStopL
                float rBtm = stBullL ? stStopL : stEntryL
                float wTop = stBullL ? stTargetL : stEntryL
                float wBtm = stBullL ? stEntryL : stTargetL
                visOut.bxRisk := box.new(actualEntryBar, rTop, bar_index, rBtm, border_color = color(na), xloc = xloc.bar_index, bgcolor = rrRiskC)
                visOut.bxReward := box.new(actualEntryBar, wTop, bar_index, wBtm, border_color = color(na), xloc = xloc.bar_index, bgcolor = rrRewardC)
                visOut.lnEntry := line.new(actualEntryBar, stEntryL, bar_index, stEntryL, xloc.bar_index, color = rrEntryC, style = line.style_dotted)
                visOut.lnStop := line.new(actualEntryBar, stStopL, bar_index, stStopL, xloc.bar_index, color = rrStopC, style = line.style_solid)
                visOut.lnTarget := line.new(actualEntryBar, stTargetL, bar_index, stTargetL, xloc.bar_index, color = rrTargetC, style = line.style_dashed)
    [newFill, startedTradesL, orderPendingL, stBullL, stEntryL, stStopL, stQtyL, stTargetL, stSessNameL, visOut]

f_handle_closed_trade(int processedN, float pnlDay, float pAsia, float pLondon, float pNYAM, float pNYPM, int wins, int losses, TradeVis visIn) =>
    int processedL = processedN
    float dayPnLL = pnlDay
    float pnlAsiaL = pAsia
    float pnlLondonL = pLondon
    float pnlNYAML = pNYAM
    float pnlNYPML = pNYPM
    int dayWinsL = wins
    int dayLossesL = losses
    TradeVis visOut = visIn
    if strategy.closedtrades > processedL
        int lastClosed = strategy.closedtrades - 1
        float closedProfit = strategy.closedtrades.profit(lastClosed)
        int closedExitBar = strategy.closedtrades.exit_bar_index(lastClosed)
        dayPnLL += closedProfit
        if stSessName == "ASIA"
            pnlAsiaL += closedProfit
        else if stSessName == "LONDON"
            pnlLondonL += closedProfit
        else if stSessName == "NYAM"
            pnlNYAML += closedProfit
        else if stSessName == "NYPM"
            pnlNYPML += closedProfit
        if closedProfit > 0
            dayWinsL += 1
        else if closedProfit < 0
            dayLossesL += 1
        if not na(visOut)
            if rrSH and not na(visOut.bxRisk)
                visOut.bxRisk.set_right(closedExitBar)
                visOut.bxReward.set_right(closedExitBar)
                visOut.lnEntry.set_x2(closedExitBar)
                visOut.lnStop.set_x2(closedExitBar)
                visOut.lnTarget.set_x2(closedExitBar)
            visHist.unshift(visOut)
            if visHist.size() > rrKeep
                TradeVis old = visHist.pop()
                if not na(old.bxRisk)
                    old.bxRisk.delete()
                if not na(old.bxReward)
                    old.bxReward.delete()
                if not na(old.lnEntry)
                    old.lnEntry.delete()
                if not na(old.lnStop)
                    old.lnStop.delete()
                if not na(old.lnTarget)
                    old.lnTarget.delete()
                if not na(old.lbEntry)
                    old.lbEntry.delete()
        visOut := na
        processedL := strategy.closedtrades
    [processedL, dayPnLL, pnlAsiaL, pnlLondonL, pnlNYAML, pnlNYPML, dayWinsL, dayLossesL, visOut]

f_update_open_visuals() =>
    if rrSH and strategy.position_size != 0 and not na(stVis)
        if not na(stVis.bxRisk)
            stVis.bxRisk.set_right(bar_index)
            stVis.bxReward.set_right(bar_index)
            stVis.lnEntry.set_x2(bar_index)
            stVis.lnStop.set_x2(bar_index)
            stVis.lnTarget.set_x2(bar_index)

f_draw_dashboard(table dashTable) =>
    if barstate.islast and dashShow
        string dayPnLText = (dayPnL >= 0 ? "+$" : "-$") + str.tostring(math.abs(dayPnL), "#.##")
        string dayWinRateText = (dayWins + dayLosses) > 0 ? str.tostring(dayWins / (dayWins + dayLosses) * 100.0, "#") + "%" : "—"
        string dayTradesText = str.tostring(dayTrades)
        float bestVal = pnlAsia
        string bestName = "Asia"
        if pnlLondon > bestVal
            bestVal := pnlLondon
            bestName := "London"
        if pnlNYAM > bestVal
            bestVal := pnlNYAM
            bestName := "NY AM"
        if pnlNYPM > bestVal
            bestVal := pnlNYPM
            bestName := "NY PM"
        string bestSessionText = dayTrades == 0 ? "—" : bestName
        table.cell(dashTable, 0, 0, "PERFORMANCE", text_color = dashLabelColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 1, 0, "", bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 0, 1, "Net PnL", text_color = dashLabelColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 1, 1, dayPnLText, text_color = dayPnL >= 0 ? dashPositiveColor : dashNegativeColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 0, 2, "Win Rate", text_color = dashLabelColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 1, 2, dayWinRateText, text_color = dashValueColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 0, 3, "Trades Today", text_color = dashLabelColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 1, 3, dayTradesText, text_color = dashValueColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 0, 4, "Best Session", text_color = dashLabelColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))
        table.cell(dashTable, 1, 4, bestSessionText, text_color = dashPositiveColor, text_size = dashTextSize, bgcolor = color.new(dashBgColor, dashBgTransp))

etDayKey = year(time, kzTZ) * 10000 + month(time, kzTZ) * 100 + dayofmonth(time, kzTZ)
if bar_index > 0 and etDayKey != etDayKey[1]
    v15CountToday := 0
    dayTrades := 0
    dayLosses := 0
    dayWins := 0
    dayPnL := 0
    pnlAsia := 0
    pnlLondon := 0
    pnlNYAM := 0
    pnlNYPM := 0

if sessStarted
    runHi := high
    runLo := low

[_v15N, _runHi, _runLo, _pStop, _pLong, _pSess, _pOrder] = f_eval_candidate(v15CountToday, runHi, runLo, pendingStop, pendingLong, pendingSess, orderPending)
v15CountToday := _v15N
runHi := _runHi
runLo := _runLo
pendingStop := _pStop
pendingLong := _pLong
pendingSess := _pSess
orderPending := _pOrder

[newFill, _started, _orderAfterFill, _stBull, _stEntry, _stStop, _stQty, _stTarget, _stSess, _stVis] = f_handle_fill(startedTrades, pendingStop, pendingLong, pendingSess, orderPending, stVis)
startedTrades := _started
orderPending := _orderAfterFill
stBull := _stBull
stEntry := _stEntry
stStop := _stStop
stQty := _stQty
stTarget := _stTarget
stSessName := _stSess
stVis := _stVis
if newFill
    dayTrades += 1

[_processed, _dayPnL, _pAsia, _pLondon, _pNYAM, _pNYPM, _wins, _losses, _closedVis] = f_handle_closed_trade(processedClosedTrades, dayPnL, pnlAsia, pnlLondon, pnlNYAM, pnlNYPM, dayWins, dayLosses, stVis)
processedClosedTrades := _processed
dayPnL := _dayPnL
pnlAsia := _pAsia
pnlLondon := _pLondon
pnlNYAM := _pNYAM
pnlNYPM := _pNYPM
dayWins := _wins
dayLosses := _losses
stVis := _closedVis
f_update_open_visuals()

var table dashTable = table.new(dashPos, 2, 5, bgcolor = color.new(dashBgColor, dashBgTransp), frame_color = color.new(dashBorderColor, dashBorderTransp), frame_width = 1)
f_draw_dashboard(dashTable)

if barstate.islast and timeframe.in_seconds() != 180
    runtime.error("The Icon Frozen Option 2A must run on the 3-minute chart.")
'''

OUT.write_text(HEADER + "\n" + v15 + "\n" + ENGINE)
print(f"CREATED {OUT}")
print(f"SIZE {OUT.stat().st_size} bytes")
print("Next: paste/compile in TradingView with PickMyTrade disabled.")