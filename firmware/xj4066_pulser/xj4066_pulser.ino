//==============================================================================
// 瞬迹 / XunJi — CD4066 动态线束 µs 脉冲源（16 路独立 · V2）
//  Arduino Nano (ATmega328P @ 16 MHz)
//
//  ★ V2 相对 V1 的变化
//    1) 上电 / 复位后【自动开始演示】，不依赖串口命令 —— 复位键=重新演示
//    2) 自动演示：轮流打断 ch0→ch15，每路停留 1 s，期间按 100 µs / 500 µs 打脉冲
//       （占空 20%，FPGA 侧稳定捕获，上位机 12 s 历史条可见缺口）
//    3) A5 按键：短按=演示开/关；长按(>500ms)=16 路同时单发 100 µs
//       ⚠ 按键必须接 A5，不能接 D2-D13/A0-A3（那些是 16 路控制线）
//    4) A4 = MARKER 同步输出（脉冲期间拉高），供示波器/将来 FPGA 触发
//
//  电平语义（CD4066B）
//    控制脚 HIGH（>=3.5 V） = 开关闭合 = 线束【通】
//    控制脚 LOW             = 开关断开 = 线束【断】
//  上电默认：全部 HIGH = 全部导通（安全态）
//
//  引脚映射（ch0..ch15 依次）：
//    ch0..ch5  -> D2..D7    (PORTD bit2..7)
//    ch6..ch11 -> D8..D13   (PORTB bit0..5)
//    ch12..ch15-> A0..A3    (PORTC bit0..3)
//    MARKER    -> A4        (PORTC bit4)   脉冲期间拉高
//    按键      -> A5        (PC5, INPUT_PULLUP，接 A5 与 GND)
//
//  串口 115200 8N1，行结束 \r 或 \n
//    ?                        打印状态
//    C                        全部闭合（全通）
//    O                        全部断开（全断）
//    P <ch> <us>              单通道断 us 微秒后恢复        例: P 7 10
//    G <g> <us>               组 g(0..3)=ch4g..4g+3 同时断   例: G 1 10
//    A <us>                   16 路同时断                   例: A 10
//    R <ch> <us> <period_us>  单通道周期脉冲                例: R 7 100 500
//    H <g> <us> <period_us>   组周期脉冲
//    E <us> <period_us>       16 路同时周期脉冲
//    K <ch> <1|0>             锁定：1=断开保持  0=闭合
//    M                        自动演示开（轮流 ch0..ch15）
//    Z                        自动演示关（全通）
//    S                        停止所有周期/演示，恢复全通
//==============================================================================

#include <Arduino.h>

static const uint8_t PIN_BTN    = A5;   // 按键（A5 与 GND）
static const uint8_t PIN_MARKER = A4;   // 同步输出

static uint16_t state = 0xFFFF;         // 1 = 闭合(通)
static uint32_t pulse_count = 0;

// ---- 单通道写电平（只动目标位，不碰 UART/晶振位）--------------------------
static inline void chWrite(uint8_t ch, bool high)
{
    if (ch < 6) {
        uint8_t m = (uint8_t)(1u << (ch + 2));
        if (high) PORTD |= m; else PORTD &= (uint8_t)~m;
    } else if (ch < 12) {
        uint8_t m = (uint8_t)(1u << (ch - 6));
        if (high) PORTB |= m; else PORTB &= (uint8_t)~m;
    } else {
        uint8_t m = (uint8_t)(1u << (ch - 12));
        if (high) PORTC |= m; else PORTC &= (uint8_t)~m;
    }
}

static void applyState()
{
    PORTD = (uint8_t)((PORTD & 0x03) | (uint8_t)((state & 0x003F) << 2));
    PORTB = (uint8_t)((PORTB & 0xC0) | (uint8_t)((state >> 6) & 0x003F));
    PORTC = (uint8_t)((PORTC & 0xC0) | (uint8_t)((state >> 12) & 0x000F));
}

static void setCh(uint8_t ch, bool closed)
{
    if (closed) state |=  (uint16_t)(1u << ch);
    else        state &= (uint16_t)~(1u << ch);
    chWrite(ch, closed);
}

static inline void markerOn()  { PORTC |=  0x10; }
static inline void markerOff() { PORTC &= (uint8_t)~0x10; }

// ---- 脉冲 ----------------------------------------------------------------
static void pulseCh(uint8_t ch, uint16_t us)
{
    if (us == 0) us = 1;
    uint16_t m = (uint16_t)(1u << ch);
    bool was = (state & m) != 0;

    markerOn();
    if (us <= 200) {
        uint8_t sreg = SREG;
        cli();
        chWrite(ch, false);
        delayMicroseconds(us);
        chWrite(ch, was);
        SREG = sreg;
    } else {
        chWrite(ch, false);
        delayMicroseconds(us);
        chWrite(ch, was);
    }
    markerOff();
    pulse_count++;
}

static void pulseGroup(uint8_t g, uint16_t us)
{
    if (us == 0) us = 1;
    uint8_t base = (uint8_t)(g * 4);
    markerOn();
    if (us <= 200) {
        uint8_t sreg = SREG;
        cli();
        for (uint8_t i = 0; i < 4; i++) chWrite((uint8_t)(base + i), false);
        delayMicroseconds(us);
        for (uint8_t i = 0; i < 4; i++) chWrite((uint8_t)(base + i), (state >> (base + i)) & 1);
        SREG = sreg;
    } else {
        for (uint8_t i = 0; i < 4; i++) chWrite((uint8_t)(base + i), false);
        delayMicroseconds(us);
        for (uint8_t i = 0; i < 4; i++) chWrite((uint8_t)(base + i), (state >> (base + i)) & 1);
    }
    markerOff();
    pulse_count++;
}

static void pulseAll(uint16_t us)
{
    if (us == 0) us = 1;
    markerOn();
    if (us <= 200) {
        uint8_t sreg = SREG;
        cli();
        PORTD &= 0x03; PORTB &= 0xC0; PORTC &= 0xCF;
        delayMicroseconds(us);
        PORTD |= (uint8_t)((state & 0x003F) << 2);
        PORTB |= (uint8_t)((state >> 6) & 0x003F);
        PORTC |= (uint8_t)((state >> 12) & 0x000F);
        SREG = sreg;
    } else {
        PORTD &= 0x03; PORTB &= 0xC0; PORTC &= 0xCF;
        delayMicroseconds(us);
        PORTD |= (uint8_t)((state & 0x003F) << 2);
        PORTB |= (uint8_t)((state >> 6) & 0x003F);
        PORTC |= (uint8_t)((state >> 12) & 0x000F);
    }
    markerOff();
    pulse_count++;
}

// ---- 周期 / 演示 ---------------------------------------------------------
static bool     repeating  = false;
static uint8_t  rep_mode   = 0;      // 0=单通道 1=组 2=全部
static uint8_t  rep_ch     = 0;
static uint16_t rep_width  = 100;
static uint32_t rep_period = 500;
static uint32_t rep_last   = 0;

static bool     autodemo   = true;   // ★ 上电默认开启
static uint8_t  ad_ch      = 0;
static uint32_t ad_last    = 0;
static uint32_t ad_step_ms = 0;
static const uint16_t AD_WIDTH  = 100;    // µs
static const uint32_t AD_PERIOD = 500;    // µs
static const uint32_t AD_STEP   = 1000;   // 每路停留 ms

static void doRepeatPulse()
{
    if (rep_mode == 0)      pulseCh(rep_ch, rep_width);
    else if (rep_mode == 1) pulseGroup(rep_ch, rep_width);
    else                    pulseAll(rep_width);
}

static void autodemoStart()
{
    autodemo   = true;
    repeating  = false;
    state = 0xFFFF; applyState();
    ad_ch      = 0;
    ad_last    = micros();
    ad_step_ms = millis();
}

// ---- 命令 ----------------------------------------------------------------
static char    linebuf[56];
static uint8_t linelen = 0;

static void printStatus()
{
    Serial.println(F("--- XunJi 4066 pulser (16ch, V2) ---"));
    Serial.print(F("state hex  : 0x")); Serial.println(state, HEX);
    Serial.print(F("open ch    :"));
    for (uint8_t i = 0; i < 16; i++) {
        if (!((state >> i) & 1)) { Serial.print(' '); Serial.print(i); }
    }
    Serial.println();
    Serial.print(F("repeat     : "));
    if (repeating) {
        Serial.print(rep_mode == 0 ? F("ch=") : (rep_mode == 1 ? F("grp=") : F("ALL ")));
        if (rep_mode != 2) Serial.print(rep_ch);
        Serial.print(F(" w=")); Serial.print(rep_width);
        Serial.print(F("us p=")); Serial.print(rep_period); Serial.println(F("us"));
    } else Serial.println(F("off"));
    Serial.print(F("autodemo   : "));
    if (autodemo) {
        Serial.print(F("ON ch=")); Serial.print(ad_ch);
        Serial.print(F(" w=")); Serial.print(AD_WIDTH);
        Serial.print(F("us p=")); Serial.print(AD_PERIOD);
        Serial.print(F("us step=")); Serial.print(AD_STEP); Serial.println(F("ms"));
    } else Serial.println(F("off"));
    Serial.print(F("pulses     : ")); Serial.println(pulse_count);
    Serial.println(F("cmds: ? C O P G A R H E K M Z S"));
}

static void handleLine(char *s)
{
    while (*s == ' ' || *s == '\t') s++;
    if (*s == 0) return;
    char c = *s;
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');

    if (c == '?') { printStatus(); return; }

    if (c == 'C') { autodemo = false; repeating = false; state = 0xFFFF; applyState();
                    Serial.println(F("OK all closed")); return; }
    if (c == 'O') { autodemo = false; repeating = false; state = 0x0000; applyState();
                    Serial.println(F("OK all open")); return; }
    if (c == 'S') { autodemo = false; repeating = false; state = 0xFFFF; applyState();
                    Serial.println(F("OK stopped, all closed")); return; }
    if (c == 'Z') { autodemo = false; repeating = false; state = 0xFFFF; applyState();
                    Serial.println(F("OK autodemo off")); return; }
    if (c == 'M') { autodemoStart();
                    Serial.println(F("OK autodemo ON: rotate ch0..15, 100us @500us, 1s/step")); return; }

    if (c == 'P') {
        int ch = -1; unsigned long us = 0;
        if (sscanf(s, "%*c %d %lu", &ch, &us) == 2 && ch >= 0 && ch <= 15 && us <= 65535) {
            pulseCh((uint8_t)ch, (uint16_t)us);
            Serial.print(F("OK P ch=")); Serial.print(ch);
            Serial.print(F(" us=")); Serial.println(us);
        } else Serial.println(F("ERR usage: P <0..15> <us>"));
        return;
    }
    if (c == 'G') {
        int g = -1; unsigned long us = 0;
        if (sscanf(s, "%*c %d %lu", &g, &us) == 2 && g >= 0 && g <= 3 && us <= 65535) {
            pulseGroup((uint8_t)g, (uint16_t)us);
            Serial.print(F("OK G g=")); Serial.print(g);
            Serial.print(F(" us=")); Serial.println(us);
        } else Serial.println(F("ERR usage: G <0..3> <us>"));
        return;
    }
    if (c == 'A') {
        unsigned long us = 0;
        if (sscanf(s, "%*c %lu", &us) == 1 && us <= 65535) {
            pulseAll((uint16_t)us);
            Serial.print(F("OK A us=")); Serial.println(us);
        } else Serial.println(F("ERR usage: A <us>"));
        return;
    }
    if (c == 'R') {
        int ch = -1; unsigned long us = 0, per = 0;
        if (sscanf(s, "%*c %d %lu %lu", &ch, &us, &per) == 3 &&
            ch >= 0 && ch <= 15 && us <= 65535 && per >= 100) {
            autodemo = false;
            rep_mode = 0; rep_ch = (uint8_t)ch; rep_width = (uint16_t)us; rep_period = (uint32_t)per;
            rep_last = micros(); repeating = true; state = 0xFFFF; applyState();
            Serial.print(F("OK R ch=")); Serial.print(ch);
            Serial.print(F(" us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else Serial.println(F("ERR usage: R <0..15> <us> <period_us>=100..>"));
        return;
    }
    if (c == 'H') {
        int g = -1; unsigned long us = 0, per = 0;
        if (sscanf(s, "%*c %d %lu %lu", &g, &us, &per) == 3 &&
            g >= 0 && g <= 3 && us <= 65535 && per >= 400) {
            autodemo = false;
            rep_mode = 1; rep_ch = (uint8_t)g; rep_width = (uint16_t)us; rep_period = (uint32_t)per;
            rep_last = micros(); repeating = true; state = 0xFFFF; applyState();
            Serial.print(F("OK H g=")); Serial.print(g);
            Serial.print(F(" us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else Serial.println(F("ERR usage: H <0..3> <us> <period_us>=400..>"));
        return;
    }
    if (c == 'E') {
        unsigned long us = 0, per = 0;
        if (sscanf(s, "%*c %lu %lu", &us, &per) == 2 && us <= 65535 && per >= 400) {
            autodemo = false;
            rep_mode = 2; rep_width = (uint16_t)us; rep_period = (uint32_t)per;
            rep_last = micros(); repeating = true; state = 0xFFFF; applyState();
            Serial.print(F("OK E us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else Serial.println(F("ERR usage: E <us> <period_us>=400..>"));
        return;
    }
    if (c == 'K') {
        int ch = -1, v = -1;
        if (sscanf(s, "%*c %d %d", &ch, &v) == 2 && ch >= 0 && ch <= 15) {
            autodemo = false; repeating = false;
            setCh((uint8_t)ch, v != 0);
            Serial.print(F("OK K ch=")); Serial.print(ch);
            Serial.print(F(" ")); Serial.println(v != 0 ? F("closed") : F("OPEN"));
        } else Serial.println(F("ERR usage: K <0..15> <1|0>"));
        return;
    }

    Serial.print(F("ERR unknown: ")); Serial.println(c);
}

// ---- setup / loop --------------------------------------------------------
void setup()
{
    pinMode(PIN_MARKER, OUTPUT);
    markerOff();
    pinMode(PIN_BTN, INPUT_PULLUP);

    // 控制脚先置高再切输出，避免上电误断
    PORTD |= 0xFC;      // PD2..PD7
    PORTB |= 0x3F;      // PB0..PB5
    PORTC |= 0x0F;      // PC0..PC3
    DDRD |= 0xFC;
    DDRB |= 0x3F;
    DDRC |= 0x3F;       // PC0..PC3 控制 + PC4 MARKER + PC5 按键
    state = 0xFFFF;
    applyState();

    Serial.begin(115200);
    Serial.println();
    Serial.println(F("XunJi 4066 pulser 16ch V2"));
    Serial.println(F("ch0-5=D2-D7  ch6-11=D8-D13  ch12-15=A0-A3"));
    Serial.println(F("MARKER=A4  BTN=A5(LOW=pressed)"));
    Serial.println(F("AUTODEMO ON @ boot: rotate ch0..ch15, 100us @500us, 1s/step"));

    // 上电即开始演示（延迟 800 ms 让 USB 枚举/串口稳定）
    ad_step_ms = millis() + 800;
    ad_last    = micros();
    autodemo   = true;
}

void loop()
{
    while (Serial.available() > 0) {
        char ch = (char)Serial.read();
        if (ch == '\r' || ch == '\n') {
            if (linelen > 0) { linebuf[linelen] = 0; handleLine(linebuf); linelen = 0; }
        } else if (linelen < (uint8_t)(sizeof(linebuf) - 1)) {
            linebuf[linelen++] = ch;
        }
    }

    uint32_t now = micros();

    // 周期脉冲
    if (repeating && (uint32_t)(now - rep_last) >= rep_period) {
        rep_last += rep_period;
        if ((uint32_t)(now - rep_last) > rep_period) rep_last = now;
        doRepeatPulse();
    }

    // 自动演示
    if (autodemo) {
        if ((uint32_t)(now - ad_last) >= AD_PERIOD) {
            ad_last += AD_PERIOD;
            if ((uint32_t)(now - ad_last) > AD_PERIOD) ad_last = now;
            pulseCh(ad_ch, AD_WIDTH);
        }
        if ((uint32_t)(millis() - ad_step_ms) >= AD_STEP) {
            ad_ch = (uint8_t)((ad_ch + 1) & 15);
            ad_step_ms = millis();
        }
    }

    // 按键
    static bool     btn_prev = HIGH;
    static uint32_t btn_down = 0;
    bool btn = digitalRead(PIN_BTN);
    if (btn == LOW && btn_prev == HIGH) btn_down = millis();
    if (btn == HIGH && btn_prev == LOW) {
        uint32_t held = millis() - btn_down;
        if (held >= 500) {
            autodemo = false; repeating = false;
            pulseAll(100);
            Serial.println(F("BTN: pulse ALL 100us"));
        } else {
            autodemo = !autodemo;
            if (autodemo) autodemoStart();
            else { state = 0xFFFF; applyState(); }
            Serial.println(autodemo ? F("BTN: autodemo ON") : F("BTN: autodemo OFF"));
        }
    }
    btn_prev = btn;
}
