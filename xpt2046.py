"""XPT2046 Touch module."""
from time import sleep

from micropython import const
class Touch(object):
    """Serial interface for XPT2046 Touch Screen Controller."""

    # Command constants from ILI9341 datasheet
    GET_X = const(0b11010000)  # X position
    GET_Y = const(0b10010000)  # Y position
    GET_Z1 = const(0b10110000)  # Z1 position
    GET_Z2 = const(0b11000000)  # Z2 position
    GET_TEMP0 = const(0b10000000)  # Temperature 0
    GET_TEMP1 = const(0b11110000)  # Temperature 1
    GET_BATTERY = const(0b10100000)  # Battery monitor
    GET_AUX = const(0b11100000)  # Auxiliary input to ADC

    def __init__(self, spi, cs, int_pin=None, int_handler=None,
                 width=240, height=320,
                 x_min=100, x_max=1962, y_min=100, y_max=1900):
        """Initialize touch screen controller.

        Args:
spi （Class Spi）： 用于 OLED 的 SPI 接口
            cs （Class Pin）：片选引脚
            int_pin （Class Pin）：触摸控制器中断引脚
            int_handler （function）：屏幕中断的处理程序
            width （int）：LCD 屏幕的宽度
            height （int）：LCD 屏幕的高度
            x_min （int）：最小 x 坐标
            x_max （int）：最大 x 坐标
            y_min （int）：最小 Y 坐标
            y_max （int）：最大 Y 坐标
        """
        self.spi = spi
        self.cs = cs
        self.cs.init(self.cs.OUT, value=1)
        self.rx_buf = bytearray(3)  # Receive buffer
        self.tx_buf = bytearray(3)  # Transmit buffer
        self.width = width
        self.height = height
        # Set calibration
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.x_multiplier = width / (x_max - x_min)
        self.x_add = x_min * -self.x_multiplier
        self.y_multiplier = height / (y_max - y_min)
        self.y_add = y_min * -self.y_multiplier

        if int_pin is not None:
            self.int_pin = int_pin
            self.int_pin.init(int_pin.IN)
            self.int_handler = int_handler
            self.int_locked = False
            int_pin.irq(trigger=int_pin.IRQ_FALLING | int_pin.IRQ_RISING,
                        handler=self.int_press)

    def get_touch(self):
        """采集多个样本以获得准确的触摸读数."""
        timeout = 2  # set timeout to 2 seconds
        confidence = 5
        buff = [[0, 0] for x in range(confidence)]
        buf_length = confidence  # Require a confidence of 5 good samples
        buffptr = 0  # Track current buffer position
        nsamples = 0  # Count samples
        while timeout > 0:
            if nsamples == buf_length:
                meanx = sum([c[0] for c in buff]) // buf_length
                meany = sum([c[1] for c in buff]) // buf_length
                dev = sum([(c[0] - meanx)**2 +
                          (c[1] - meany)**2 for c in buff]) / buf_length
                if dev <= 50:  # Deviation should be under margin of 50
                    return self.normalize(meanx, meany)
            # get a new value
            sample = self.raw_touch()  # get a touch
            if sample is None:
                nsamples = 0    # Invalidate buff
            else:
                buff[buffptr] = sample  # put in buff
                buffptr = (buffptr + 1) % buf_length  # Incr, until rollover
                nsamples = min(nsamples + 1, buf_length)  # Incr. until max

            sleep(.05)
            timeout -= .05
        return None

    def int_press(self, pin):
        """Send X,Y values to passed interrupt handler."""
        if not pin.value() and not self.int_locked:
            self.int_locked = True  # Lock Interrupt
            buff = self.raw_touch()

            if buff is not None:
                x, y = self.normalize(*buff)
                self.int_handler(x, y)
            sleep(.1)  # Debounce falling edge
        elif pin.value() and self.int_locked:
            sleep(.1)  # Debounce rising edge
            self.int_locked = False  # Unlock interrupt

    def normalize(self, x, y):
        """标准化平均 X，Y 值以匹配 LCD 屏幕。"""
        x = int(self.x_multiplier * x + self.x_add)
        y = int(self.y_multiplier * y + self.y_add)
        return x, y

    def raw_touch(self):
        """读取原始 X、Y 触摸值.

        Returns:
            tuple(int, int): X, Y
        """
        x = self.send_command(self.GET_X)
        y = self.send_command(self.GET_Y)
        if self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max:
            return (x, y)
        else:
            return None

    def send_command(self, command):
        """Write command to XT2046 (MicroPython).

        Args:
            command (byte): XT2046 command code.
        Returns:
            int: 12 bit response
        """
        self.tx_buf[0] = command
        self.cs(0)
        self.spi.write_readinto(self.tx_buf, self.rx_buf)
        self.cs(1)

        return (self.rx_buf[1] << 4) | (self.rx_buf[2] >> 4)
