//==============================================================================
// 瞬迹 / XunJi — CD4066 动态线束 µs 脉冲源
//  Arduino Nano (ATmega328P @ 16 MHz)
//
//  接线（方案 A：每颗 4066 的 4 个控制脚 13/5/6/12 并成 1 根）
//    D2 -> CTRL_U1  ch0..ch3
//    D3 -> CTRL_U2  ch4..ch7
//    D4 -> CTRL_U3  ch8..ch11
//    D5 -> CTRL_U4  ch12..ch15
//    GND -> FE-16 的 TP50 / J5-33、J5-34（必须共地！）
//    5V  -> 4066 的 VDD（pin14）
//    D6 -> 板上按键，按下 = 4 组同时打一发 10 µs 脉冲（可选）
//    D13 -> 板载 LED，脉冲时闪
//
//  电平语义（CD4066B）
//    控制脚 HIGH（>=3.5 V） = 开关闭合 = 线束【通】
//    控制脚 LOW             = 开关断开 = 线束【断】
//  上电默认：全部 HIGH = 全部导通（安全态，等价于一根完好线束）
//
//  串口 115200 8N1，行结束用 \r 或 \n
//    ?                     打印状态
//    C                     全部闭合（全通）
//    O                     全部断开（全断）
//    P <g> <us>            单发：把组 g(0..3) 断开 us 微秒后恢复
//    A <us>                单发：4 组同时断开 us 微秒
//    R <g> <us> <period_us> 周期脉冲：每 period_us 打一发 us 宽（g=0..3）
//    S                     停止周期脉冲
//    M                     演示模式：轮流打断 0→1→2→3，10 µs 宽，每 20 ms 一发
//    D <us> <period_us>    全组周期脉冲（4 组同时断）
//==============================================================================

#include <Arduino.h>

// ---- 引脚 ----------------------------------------------------------------
static const uint8_t PIN_G0 = 2;          // PD2 -> CTRL_U1
static const uint8_t PIN_G1 = 3;          // PD3 -> CTRL_U2
static const uint8_t PIN_G2 = 4;          // PD4 -> CTRL_U3
static const uint8_t PIN_G3 = 5;          // PD5 -> CTRL_U4
static const uint8_t PIN_BTN = 6;         // 可选：手动触发
static const uint8_t PIN_LED = 13;        // 板载 LED

static const uint8_t CTRL_MASK = 0x3C;    // PD2|PD3|PD4|PD5

// ---- 运行状态 ------------------------------------------------------------
static bool     repeating   = false;
static uint8_t  rep_group   = 0;
static uint16_t rep_width   = 10;         // µs
static uint32_t rep_period  = 20000;      // µs
static uint32_t rep_last    = 0;

static bool     demo_mode   = false;
static uint8_t  demo_group   = 0;
static uint32_t demo_last   = 0;
static const uint32_t DEMO_PERIOD = 20000; // 20 ms

static uint32_t pulse_count = 0;

// ---- 底层端口操作（D2..D5 全在 PORTD，单指令改电平）-----------------------
static inline void groupOn(uint8_t g)  { PORTD |=  (uint8_t)(1u << (2u + g)); }
static inline void groupOff(uint8_t g) { PORTD &= (uint8_t)~(1u << (2u + g)); }
static inline void allOn()             { PORTD |=  CTRL_MASK; }
static inline void allOff()            { PORTD &= (uint8_t)~CTRL_MASK; }

// 打一发脉冲：组 g 断开 width µs 后恢复
static void pulseGroup(uint8_t g, uint16_t width)
{
    uint8_t m = (uint8_t)(1u << (2u + g));
    if (width == 0) width = 1;

    if (width <= 200) {
        // 短脉冲：关中断保证宽度精确（1 µs = 16 个时钟）
        uint8_t sreg = SREG;
        cli();
        PORTD &= (uint8_t)~m;
        delayMicroseconds(width);
        PORTD |= m;
        SREG = sreg;
    } else {
        // 长脉冲：不关中断，避免影响串口/时基
        PORTD &= (uint8_t)~m;
        delayMicroseconds(width);
        PORTD |= m;
    }
    pulse_count++;
}

static void pulseAll(uint16_t width)
{
    if (width == 0) width = 1;
    if (width <= 200) {
        uint8_t sreg = SREG;
        cli();
        PORTD &= (uint8_t)~CTRL_MASK;
        delayMicroseconds(width);
        PORTD |= CTRL_MASK;
        SREG = sreg;
    } else {
        PORTD &= (uint8_t)~CTRL_MASK;
        delayMicroseconds(width);
        PORTD |= CTRL_MASK;
    }
    pulse_count++;
}

// ---- 命令解析 ------------------------------------------------------------
static char    linebuf[48];
static uint8_t linelen = 0;

static void printStatus()
{
    Serial.println(F("--- XunJi 4066 pulser ---"));
    Serial.print(F("state      : "));
    Serial.println((PORTD & CTRL_MASK) == CTRL_MASK ? F("ALL CLOSED (connected)")
                                                   : F("some OPEN"));
    Serial.print(F("repeat     : "));
    if (repeating) {
        Serial.print(F("group=")); Serial.print(rep_group);
        Serial.print(F(" width=")); Serial.print(rep_width);
        Serial.print(F("us period=")); Serial.print(rep_period);
        Serial.println(F("us"));
    } else {
        Serial.println(F("off"));
    }
    Serial.print(F("demo       : ")); Serial.println(demo_mode ? F("on") : F("off"));
    Serial.print(F("pulses     : ")); Serial.println(pulse_count);
    Serial.println(F("cmds: ? C O P<g> A R<g> S M D"));
}

static void handleLine(char *s)
{
    // 跳过前导空格
    while (*s == ' ' || *s == '\t') s++;
    if (*s == 0) return;

    char c = *s;
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');

    switch (c) {
    case '?':
        printStatus();
        break;

    case 'C':                                   // 全通
        repeating = false; demo_mode = false;
        allOn();
        Serial.println(F("OK all closed"));
        break;

    case 'O':                                   // 全断
        repeating = false; demo_mode = false;
        allOff();
        Serial.println(F("OK all open"));
        break;

    case 'P': {                                 // P <g> <us>
        int g = -1; unsigned long us = 0;
        if (sscanf(s, "%*c %d %lu", &g, &us) == 2 && g >= 0 && g <= 3 && us <= 65535) {
            pulseGroup((uint8_t)g, (uint16_t)us);
            Serial.print(F("OK pulse g=")); Serial.print(g);
            Serial.print(F(" us=")); Serial.println(us);
        } else {
            Serial.println(F("ERR usage: P <0..3> <us>"));
        }
        break;
    }

    case 'A': {                                 // A <us>
        unsigned long us = 0;
        if (sscanf(s, "%*c %lu", &us) == 1 && us <= 65535) {
            pulseAll((uint16_t)us);
            Serial.print(F("OK pulse ALL us=")); Serial.println(us);
        } else {
            Serial.println(F("ERR usage: A <us>"));
        }
        break;
    }

    case 'R': {                                 // R <g> <us> <period_us>
        int g = -1; unsigned long us = 0, per = 0;
        if (sscanf(s, "%*c %d %lu %lu", &g, &us, &per) == 3 &&
            g >= 0 && g <= 3 && us <= 65535 && per >= 100) {
            rep_group = (uint8_t)g;
            rep_width = (uint16_t)us;
            rep_period = (uint32_t)per;
            rep_last = micros();
            repeating = true;
            demo_mode = false;
            allOn();
            Serial.print(F("OK repeat g=")); Serial.print(g);
            Serial.print(F(" us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else {
            Serial.println(F("ERR usage: R <0..3> <us> <period_us>=100..>"));
        }
        break;
    }

    case 'S':                                   // 停止
        repeating = false; demo_mode = false;
        allOn();
        Serial.println(F("OK stopped, all closed"));
        break;

    case 'M':                                   // 演示：轮流打断
        repeating = false;
        demo_mode = true;
        demo_group = 0;
        demo_last = micros();
        allOn();
        Serial.println(F("OK demo mode (cycle groups, 10us @20ms)"));
        break;

    case 'D': {                                 // D <us> <period_us> 全组周期
        unsigned long us = 0, per = 0;
        if (sscanf(s, "%*c %lu %lu", &us, &per) == 2 &&
            us <= 65535 && per >= 100) {
            rep_width = (uint16_t)us;
            rep_period = (uint32_t)per;
            rep_last = micros();
            repeating = true;
            demo_mode = false;
            rep_group = 0xFF;                   // 特殊值：全组
            allOn();
            Serial.print(F("OK repeat ALL us=")); Serial.print(us);
            Serial.print(F(" period=")); Serial.print(per); Serial.println(F("us"));
        } else {
            Serial.println(F("ERR usage: D <us> <period_us>=100..>"));
        }
        break;
    }

    default:
        Serial.print(F("ERR unknown: ")); Serial.println(c);
        break;
    }
}

// ---- setup / loop --------------------------------------------------------
void setup()
{
    // 先把控制脚置高（导通）再切输出，避免上电瞬间误断
    PORTD |= CTRL_MASK;
    pinMode(PIN_G0, OUTPUT);
    pinMode(PIN_G1, OUTPUT);
    pinMode(PIN_G2, OUTPUT);
    pinMode(PIN_G3, OUTPUT);
    allOn();

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_BTN, INPUT_PULLUP);

    Serial.begin(115200);
    Serial.println();
    Serial.println(F("XunJi CD4066 pulser ready. state=ALL CLOSED"));
    Serial.println(F("D2-D5 = CTRL_U1..U4 (HIGH=closed). cmd: ? "));
}

void loop()
{
    // ---- 串口命令 ----
    while (Serial.available() > 0) {
        char ch = (char)Serial.read();
        if (ch == '\r' || ch == '\n') {
            if (linelen > 0) {
                linebuf[linelen] = 0;
                handleLine(linebuf);
                linelen = 0;
            }
        } else if (linelen < (uint8_t)(sizeof(linebuf) - 1)) {
            linebuf[linelen++] = ch;
        }
    }

    // ---- 按键：4 组同时 10 µs ----
    static bool btn_prev = HIGH;
    bool btn = digitalRead(PIN_BTN);
    if (btn == LOW && btn_prev == HIGH) {
        pulseAll(10);
        digitalWrite(PIN_LED, HIGH);
        Serial.println(F("BTN: pulse ALL 10us"));
    }
    btn_prev = btn;

    // ---- 周期脉冲 ----
    if (repeating) {
        uint32_t now = micros();
        if ((uint32_t)(now - rep_last) >= rep_period) {
            rep_last += rep_period;
            // 防止落后太多后爆发式补脉冲
            if ((uint32_t)(now - rep_last) > rep_period) rep_last = now;

            if (rep_group == 0xFF) pulseAll(rep_width);
            else                   pulseGroup(rep_group, rep_width);
        }
    }

    // ---- 演示模式：轮流打断 ----
    if (demo_mode) {
        uint32_t now = micros();
        if ((uint32_t)(now - demo_last) >= DEMO_PERIOD) {
            demo_last = now;
            pulseGroup(demo_group, 10);
            demo_group = (uint8_t)((demo_group + 1) & 3);
        }
    }

    // ---- LED：周期性脉冲时闪一下（非阻塞）----
    static uint32_t led_off_at = 0;
    if (pulse_count != 0 && led_off_at == 0) {
        // 由脉冲触发（简化：每 50 发闪一次）
    }
    digitalWrite(PIN_LED, ((pulse_count & 0x01) && (repeating || demo_mode)) ? HIGH : LOW);
}
