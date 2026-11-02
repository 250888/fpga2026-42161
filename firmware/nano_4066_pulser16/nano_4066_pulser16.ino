//==============================================================================
// 瞬迹 / XunJi — CD4066 动态线束 µs 脉冲源（方案 B：16 路独立）
//  Arduino Nano (ATmega328P @ 16 MHz)
//
//  电平语义（CD4066B）
//    控制脚 HIGH（>=3.5 V） = 开关闭合 = 线束【通】
//    控制脚 LOW             = 开关断开 = 线束【断】
//  上电默认：全部 HIGH = 全部导通（安全态，等价于一根完好线束）
//
//  引脚映射（ch0..ch15 依次）：
//    ch0..ch5  -> D2..D7    (PORTD bit2..7)
//    ch6..ch11 -> D8..D13   (PORTB bit0..5)
//    ch12..ch15-> A0..A3    (PORTC bit0..3)
//
//  与 4 颗 CD4066 的对应（每颗 4 个开关，控制脚 13/5/6/12）：
//    U1 : ch0->13  ch1->5  ch2->6   ch3->12
//    U2 : ch4->13  ch5->5  ch6->6   ch7->12
//    U3 : ch8->13  ch9->5  ch10->6  ch11->12
//    U4 : ch12->13 ch13->5 ch14->6  ch15->12
//  四颗的 14=VDD 接 5V、7=VSS 接 GND，且必须与 FE-16 共地（TP50 / J5-33、34）
//
//  串口 115200 8N1，行结束 \r 或 \n
//    ?                        打印状态
//    C                        全部闭合（全通）
//    O                        全部断开（全断）
//    P <ch> <us>              单通道断 us 微秒后恢复        例: P 7 10
//    G <g> <us>               组 g(0..3)=ch4g..4g+3 同时断   例: G 1 10
//    A <us>                   16 路同时断                   例: A 10
//    R <ch> <us> <period_us>  单通道周期脉冲                例: R 7 10 1000
//    H <g> <us> <period_us>   组周期脉冲
//    E <us> <period_us>       16 路同时周期脉冲
//    K <ch> <1|0>             锁定：1=断开保持  0=闭合
//    M                        演示：轮流打断 ch0..ch15，10us @20ms
//    S                        停止所有周期/演示，恢复全通
//==============================================================================

#include <Arduino.h>

static uint16_t state = 0xFFFF;   // 1 = 闭合(通)，0 = 断开
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

// 把 state 整体刷到端口
static void applyState()
{
    PORTD = (uint8_t)((PORTD & 0x03) | (uint8_t)((state & 0x003F) << 2));
    PORTB = (uint8_t)((PORTB & 0xC0) | (uint8_t)((state >> 6) & 0x003F));
    PORTC = (uint8_t)((PORTC & 0xF0) | (uint8_t)((state >> 12) & 0x000F));
}

static void setCh(uint8_t ch, bool closed)
{
    if (closed) state |=  (uint16_t)(1u << ch);
    else        state &= (uint16_t)~(1u << ch);
    chWrite(ch, closed);
}

// ---- 脉冲 ----------------------------------------------------------------
static void pulseCh(uint8_t ch, uint16_t us)
{
    if (us == 0) us = 1;
    uint16_t m = (uint16_t)(1u << ch);
    bool was = (state & m) != 0;

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
    pulse_count++;
}

static void pulseGroup(uint8_t g, uint16_t us)
{
    if (us == 0) us = 1;
    uint8_t base = (uint8_t)(g * 4);
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
    pulse_count++;
}

static void pulseAll(uint16_t us)
{
    if (us == 0) us = 1;
    if (us <= 200) {
        uint8_t sreg = SREG;
        cli();
        PORTD &= 0x03;    // 清 PD2..PD7
        PORTB &= 0xC0;    // 清 PB0..PB5
        PORTC &= 0xF0;    // 清 PC0..PC3
        delayMicroseconds(us);
        PORTD |= (uint8_t)(state & 0x003F) << 2;
        PORTB |= (uint8_t)((state >> 6) & 0x003F);
        PORTC |= (uint8_t)((state >> 12) & 0x000F);
        SREG = sreg;
    } else {
        PORTD &= 0x03; PORTB &= 0xC0; PORTC &= 0xF0;
        delayMicroseconds(us);
        PORTD |= (uint8_t)(state & 0x003F) << 2;
        PORTB |= (uint8_t)((state >> 6) & 0x003F);
        PORTC |= (uint8_t)((state >> 12) & 0x000F);
    }
    pulse_count++;
}

// ---- 周期 / 演示 ---------------------------------------------------------
static bool     repeating  = false;
static uint8_t  rep_mode   = 0;      // 0=单通道 1=组 2=全部
static uint8_t  rep_ch     = 0;
static uint16_t rep_width  = 10;
static uint32_t rep_period = 20000;
static uint32_t rep_last   = 0;

static bool     demo_mode  = false;
static uint8_t  demo_ch    = 0;
static uint32_t demo_last  = 0;

static void doRepeatPulse()
{
    if (rep_mode == 0)      pulseCh(rep_ch, rep_width);
    else if (rep_mode == 1) pulseGroup(rep_ch, rep_width);
    else                    pulseAll(rep_width);
}

// ---- 命令 ----------------------------------------------------------------
static char    linebuf[56];
static uint8_t linelen = 0;

static void printStatus()
{
    Serial.println(F("--- XunJi 4066 pulser (16ch) ---"));
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
        Serial.print(F(" width=")); Serial.print(rep_width);
        Serial.print(F("us period=")); Serial.print(rep_period); Serial.println(F("us"));
    } else Serial.println(F("off"));
    Serial.print(F("demo       : ")); Serial.println(demo_mode ? F("on") : F("off"));
    Serial.print(F("pulses     : ")); Serial.println(pulse_count);
    Serial.println(F("cmds: ? C O P G A R H E K M S"));
}

static void handleLine(char *s)
{
    while (*s == ' ' || *s == '\t') s++;
    if (*s == 0) return;
    char c = *s;
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');

    if (c == '?') { printStatus(); return; }

    if (c == 'C') { repeating = false; demo_mode = false; state = 0xFFFF; applyState();
                    Serial.println(F("OK all closed")); return; }
    if (c == 'O') { repeating = false; demo_mode = false; state = 0x0000; applyState();
                    Serial.println(F("OK all open")); return; }
    if (c == 'S') { repeating = false; demo_mode = false; state = 0xFFFF; applyState();
                    Serial.println(F("OK stopped, all closed")); return; }

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
            rep_mode = 0; rep_ch = (uint8_t)ch; rep_width = (uint16_t)us; rep_period = (uint32_t)per;
            rep_last = micros(); repeating = true; demo_mode = false; state = 0xFFFF; applyState();
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
            rep_mode = 1; rep_ch = (uint8_t)g; rep_width = (uint16_t)us; rep_period = (uint32_t)per;
            rep_last = micros(); repeating = true; demo_mode = false; state = 0xFFFF; applyState();
            Serial.print(F("OK H g=")); Serial.print(g);
            Serial.print(F(" us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else Serial.println(F("ERR usage: H <0..3> <us> <period_us>=400..>"));
        return;
    }
    if (c == 'E') {
        unsigned long us = 0, per = 0;
        if (sscanf(s, "%*c %lu %lu", &us, &per) == 2 && us <= 65535 && per >= 400) {
            rep_mode = 2; rep_width = (uint16_t)us; rep_period = (uint32_t)per;
            rep_last = micros(); repeating = true; demo_mode = false; state = 0xFFFF; applyState();
            Serial.print(F("OK E us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else Serial.println(F("ERR usage: E <us> <period_us>=400..>"));
        return;
    }
    if (c == 'K') {
        int ch = -1, v = -1;
        if (sscanf(s, "%*c %d %d", &ch, &v) == 2 && ch >= 0 && ch <= 15) {
            setCh((uint8_t)ch, v != 0);
            Serial.print(F("OK K ch=")); Serial.print(ch);
            Serial.print(F(" ")); Serial.println(v != 0 ? F("closed") : F("OPEN"));
        } else Serial.println(F("ERR usage: K <0..15> <1|0>"));
        return;
    }
    if (c == 'M') {
        repeating = false; demo_mode = true; demo_ch = 0; demo_last = micros();
        state = 0xFFFF; applyState();
        Serial.println(F("OK demo: cycle ch0..15, 10us @20ms"));
        return;
    }

    Serial.print(F("ERR unknown: ")); Serial.println(c);
}

// ---- setup / loop --------------------------------------------------------
void setup()
{
    // 先置高再切输出，避免上电误断
    PORTD |= 0xFC;      // PD2..PD7 高
    PORTB |= 0x3F;      // PB0..PB5 高
    PORTC |= 0x0F;      // PC0..PC3 高

    DDRD |= 0xFC;
    DDRB |= 0x3F;
    DDRC |= 0x0F;

    state = 0xFFFF;
    applyState();

    Serial.begin(115200);
    Serial.println();
    Serial.println(F("XunJi 4066 pulser 16ch ready. all CLOSED (connected)."));
    Serial.println(F("ch0-5=D2-D7  ch6-11=D8-D13  ch12-15=A0-A3"));
    Serial.println(F("cmd: ?  (then C/O/P/G/A/R/H/E/K/M/S)"));
}

void loop()
{
    // 串口
    while (Serial.available() > 0) {
        char ch = (char)Serial.read();
        if (ch == '\r' || ch == '\n') {
            if (linelen > 0) { linebuf[linelen] = 0; handleLine(linebuf); linelen = 0; }
        } else if (linelen < (uint8_t)(sizeof(linebuf) - 1)) {
            linebuf[linelen++] = ch;
        }
    }

    uint32_t now = micros();

    if (repeating && (uint32_t)(now - rep_last) >= rep_period) {
        rep_last += rep_period;
        if ((uint32_t)(now - rep_last) > rep_period) rep_last = now;
        doRepeatPulse();
    }

    if (demo_mode && (uint32_t)(now - demo_last) >= 20000UL) {
        demo_last = now;
        pulseCh(demo_ch, 10);
        demo_ch = (uint8_t)((demo_ch + 1) & 15);
    }
}
