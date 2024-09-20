
from ili9341 import Display, color565
from xglcd_font import XglcdFont
from xpt2046 import Touch
from machine import idle, Pin, SPI, PWM, I2C, ADC
import ina226

# # I2C(INA226的实例化)
# i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)
# ina = ina226.INA226(i2c, 0x40, Rs=0.002, voltfactor=2)
# ina.set_calibration_custom(calValue=2560)
# ina.set_current_lsb(0.001)
# v, i, p = ina.get_VIP()
# V_real = '%2.2f' % v
# I_real = '%2.2f' % i
# P_real = '%2.2f' % p


# adc = ADC(Pin(6))
# v = (adc.read_u16() * 3.3 / 65535) * 4
# V_real = '%2.2f' % v


# 加载字体
unispace = XglcdFont('fonts/Unispace12x24.c', 12, 24)
# spi(屏幕与触摸的实例化)
spi = SPI(1, baudrate=40_000_000, sck=Pin(9), mosi=Pin(10))
display = Display(spi, dc=Pin(11), cs=Pin(13), rst=Pin(12))
spi2 = SPI(2, baudrate=1_000_000, sck=Pin(1), mosi=Pin(42), miso=Pin(41))
# PWM (调节电流电压) 20k < f <100k
PWM_V = PWM(Pin(3), freq=30_000,duty_u16=0)  # 30k Hz
PWM_I = PWM(Pin(8), freq=30_000,duty_u16=0)  # 30k Hz


class VA_VALUE(object):
    """Touchscreen simple demo with button detection."""
    CYAN = color565(0, 255, 255)
    PURPLE = color565(255, 0, 255)
    WHITE = color565(255, 255, 255)
    ORANGE = color565(255, 110, 0)
    VIOLET = color565(255, 18, 220)

    def __init__(self, display, spi2):
        """Initialize box.

        Args:
            display (ILI9341): display object
            spi2 (SPI): SPI bus
        """
        self.display = display
        self.touch = Touch(spi2, cs=Pin(2), int_pin=Pin(40),
                           int_handler=self.touch_screen_release)

        self.button_areas = {
            'ADD_V': (200, 10, 250, 40),  # 电压加减
            'SUB_V': (160, 10, 190, 40),

            'ADD_I': (200, 50, 250, 80),  # 电流加减
            'SUB_I': (160, 50, 190, 80),

            'SW': (160, 90, 190, 120),  #  切换模式
            'SET': (200, 90, 250, 120),  #  实际输出
        }
        self.flag = True  # 反转标志位
        self.tick = 0.1  #　默认间隔0.1
        self.duty_tick_v = 328  # 默认间隔0.1V
        self.duty_tick_i = 936  # 默认间隔0.1A
        self.duty_v = 0
        self.duty_i = 0
        self.draw_buttons()

        self.pid_duty_v = pid(Kp=1.0, Ki=0.1, Kd=0.01, setpoint=self.duty_v)  # 电压闭环控制
        # self.pid_duty_i = pid(Kp=1.0, Ki=0.1, Kd=0.01, setpoint=self.duty_i) # 电流开环控制

    def draw_buttons(self):
        """在屏幕上绘制按钮"""
        self.display.draw_text(200, 10, 'ADD', unispace, self.WHITE,
                               background=self.ORANGE)
        self.display.draw_text(160, 10, 'SUB', unispace, self.WHITE,
                               background=self.ORANGE)

        self.display.draw_text(200, 50, 'ADD', unispace, self.WHITE,
                               background=self.VIOLET)
        self.display.draw_text(160, 50, 'SUB', unispace, self.WHITE,
                               background=self.VIOLET)

        self.display.draw_text(160, 90, "S W", unispace, self.WHITE, background=self.ORANGE)
        self.display.draw_text(200, 90, "SET", unispace, self.WHITE, background=self.ORANGE)

        self.display.draw_text(0, 10, "V-OUT:", unispace, self.WHITE)
        self.display.draw_text(0, 50, "I-OUT:", unispace, self.WHITE)
        self.display.draw_text(0, 90, "P-OUT:", unispace, self.WHITE)

        self.vol_set = 4.00
        self.cur_set = 0.00
        self.power = self.vol_set * self.cur_set

        self.display.draw_text(70, 10, f"{self.vol_set:.2f}", unispace, self.WHITE)
        self.display.draw_text(70, 50, f"{self.cur_set:.2f}", unispace, self.WHITE)
        self.display.draw_text(70, 90, f"{self.power:.2f}", unispace, self.WHITE)

        self.display.draw_text(145, 10, "V", unispace, self.WHITE)
        self.display.draw_text(145, 50, "A", unispace, self.WHITE)
        self.display.draw_text(145, 90, "W", unispace, self.WHITE)

    def touch_screen_release(self, x, y):
        """中断函数"""
        x = self.display.width - x - 1

        for button_name, (x1, y1, x2, y2) in self.button_areas.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                print(f"Button pressed: {button_name}")
                self.display.fill_rectangle(0, 300, 60, 8, 0)
                self.display.draw_text8x8(0, 300, button_name, self.CYAN)

                # 电压设置
                if button_name == 'ADD_V':
                    self.vol_set += self.tick
                    self.duty_v += self.duty_tick_v
                    print(f"{self.duty_v:.2f}")
                    if self.vol_set > 24 or self.duty_v > 65535:
                        self.vol_set = 24
                        self.duty_v = 65535

                    self.display.fill_rectangle(70, 10, 70, 20, 0)
                    self.display.draw_text(70, 10, f"{self.vol_set:.2f}", unispace, self.WHITE)

                if button_name == 'SUB_V':
                    self.vol_set -= self.tick
                    self.duty_v -= self.duty_tick_v
                    print(f"{self.duty_v:.2f}")
                    if self.vol_set < 4 or self.duty_v < 0:
                        self.vol_set = 4
                        self.duty_v = 0

                    self.display.fill_rectangle(70, 10, 70, 20, 0)
                    self.display.draw_text(70, 10, f"{self.vol_set:.2f}", unispace, self.WHITE)

                # 电流设置
                if button_name == 'ADD_I':
                    self.cur_set += self.tick
                    self.duty_i += self.duty_tick_i
                    if self.cur_set > 7 or self.duty_i > 65535:
                        self.cur_set = 7
                        self.duty_i = 65535
                    self.display.fill_rectangle(70, 50, 70, 20, 0)
                    self.display.draw_text(70, 50, f"{self.cur_set:.2f}", unispace, self.WHITE)

                if button_name == 'SUB_I':
                    self.cur_set -= self.tick
                    self.duty_i -= self.duty_tick_i
                    if self.cur_set < 0 or self.duty_i < 0:
                        self.duty_i = 0
                        self.cur_set = 0

                    self.display.fill_rectangle(70, 50, 70, 20, 0)
                    self.display.draw_text(70, 50, f"{self.cur_set:.2f}", unispace, self.WHITE)

                # 小数位切换
                if button_name == 'SW':
                    if self.flag:
                        self.tick = 0.1
                        self.duty_tick_v = 328  # 间隔0.1V
                        self.duty_tick_i = 936  # 间隔0.1A
                    else:
                        self.tick = 1
                        self.duty_tick_v = 3277  # 间隔1V
                        self.duty_tick_i = 9364  # 间隔1A
                    self.flag = not self.flag

                # 设置

                # vout = 4 + 20 * D
                # iout = 7 * D
                if button_name == 'SET':
                    #  设置pwm输出到sc8701

                    # PWM_V.duty_u16(self.pid_duty_v.update(V_real))
                    PWM_V.duty_u16(self.duty_v)

                    print(f"PWM_V:{self.duty_v}, PWM_real:{self.duty_i}")

                    # self.display.draw_text(70, 10, f"{V_real}", unispace, self  .WHITE)
                    # self.display.draw_text(70, 50, f"{I_real}", unispace, self.WHITE)
                    # self.display.draw_text(70, 90, f"{P_real}", unispace, self.WHITE)

                # 功率显示
                self.power = self.vol_set * self.cur_set
                self.display.fill_rectangle(70, 90, 70, 20, 0)
                self.display.draw_text(70, 90, f"{self.power:.2f}", unispace, self.WHITE)

                break
        else:
            print("Touch outside button area")
            self.display.draw_text8x8(0, 310, "Touch outside button area", self.WHITE)


import time

class pid:
    def __init__(self, Kp, Ki, Kd, setpoint, min_output=0, max_output=65535):
        """
        初始化PID控制器。

        参数:
         Kp: 比例增益
         Ki: 积分增益
         Kd: 微分增益
         setpoint: 目标设定值
         min_output: 输出的最小值，默认为0
         max_output: 输出的最大值，默认为65535
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.min_output = min_output
        self.max_output = max_output

        # 上次的误差
        self.last_error = 0
        # 积分项
        self.integral = 0
        # 上次的时间戳
        self.last_time = time.time()

    def update(self, current_value) -> int:
        """
        更新PID控制器的输出。

        参数:
        - current_value: 当前测量值

        返回:
        - 输出的占空比
        """
        current_time = time.time()
        dt = current_time - self.last_time

        # 检查并转换类型
        if isinstance(self.setpoint, str):
            try:
                self.setpoint = float(self.setpoint)
            except ValueError:
                print("Error: setpoint is not a valid number")
                return 0

        if isinstance(current_value, str):
            try:
                current_value = float(current_value)
            except ValueError:
                print("Error: current_value is not a valid number")
                return 0

        error = float(self.setpoint - current_value)

        # 防止 dt 为零
        if dt == 0:
            dt = 1e-6  # 设置一个非常小的默认值

        # 计算积分项
        self.integral += error * dt
        # 计算微分项
        derivative = (error - self.last_error) / dt

        # 计算PID输出
        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative

        # 防止积分项累积过大
        if output > self.max_output:
            output = self.max_output
            self.integral = 0
        elif output < self.min_output:
            output = self.min_output
            self.integral = 0

        # 更新上次的误差和时间戳
        self.last_error = error
        self.last_time = current_time

        return int(output)



if __name__ == "__main__":

    VA_VALUE(display, spi2)
    try:
        while True:
            idle()

    except KeyboardInterrupt:
        print("\nCtrl-C pressed.  Cleaning up and exiting...")
        display.draw_text8x8(0, 300, "Ctrl-C pressed.  Cleaning up and exiting...", 0xf0f033)
    finally:
        display.cleanup()


