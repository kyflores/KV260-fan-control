from pynq import Overlay
import time

### Address Offsets
# Control and Status Register 0
TCSR0_OF = 0x0
# Load Register 0
TLR0_OF = 0x4
# Timer and Counter Register 0
TCR0_OF = 0x8

# Control and Status Register 1
TCSR1_OF = 0x10
# Load Register 1
TLR1_OF = 0x14
# Timer and Counter Register 1
TCR1 = 0x18

def _bit(position):
    return (1 << position)

def _set(value, mask):
    return value | mask

def _unset(value, mask):
    return value & (~mask)

### TCSR bit fields.
# Enable cascade mode. Does not apply to TCSR1
TCSR_CASC = _bit(11)
# Enable all timers
TCSR_ENALL =_bit(10)
# Enable PWM
TCSR_PWMA = _bit(9)
# Interrupt indicator bit
TCSR_TINT = _bit(8)
# General enable
TCSR_ENT = _bit(7)
# Interrupt enable
TCSR_ENIT = _bit(6)
# Load
TCSR_LOAD = _bit(5)
# Auto reload and hold
TCSR_ARHT = _bit(4)
# Enable external capture trigger
TCSR_CAPT = _bit(3)
# Enable external generate signal
TCSR_GENT = _bit(2)
# Up or down mode. 0 for up, 1 for down.
TCSR_UDT = _bit(1)
# Mode. 0 for generate, 1 for capture
TCSR_MDT = _bit(0)

class AxiPwmCtrl:
    """
    Userspace driver to set up the Xilinx AXI timer for PWM operation.
    Builds on PYNQ generic MMIO driver for memory access.
    Since this driver is designed to control the KV260 fan PWM, it will
    only properly support duty cycle control.

    See: https://github.com/Xilinx/embeddedsw/tree/master/XilinxProcessorIPLib/drivers/tmrctr/src
         https://www.xilinx.com/support/documentation/ip_documentation/axi_timer/v1_03_a/axi_timer_ds764.pdf
         https://www.xilinx.com/about/blogs/adaptable-advantage-blog/2021/microzed-chronicles--working-with-the-kria-som-in-vivado.html
    """
    def __init__(self, drv, debug=False):
        self.debug = debug
        self.drv = drv

        # This determines the period. Don't set it too long (big value)
        # since we're actually PWMing the DC input of the fan.
        self.max_count = 0xFF # Count up to this value for one period.

    def configure(self, duty_cycle_percent):
        self.stop()

        if duty_cycle_percent < 0.6:
            print("The built in fan will likely stall below 0.6 duty.")
            print("0.6 will be used instead.")
            duty_cycle_percent = 0.6

        # The counter value corresponds to the "off" rather than on time.
        duty_cycle_percent = 1.0 - duty_cycle_percent

        self.mut_reg_bits(TCSR0_OF, TCSR_UDT | TCSR_ARHT, TCSR_CASC | TCSR_GENT)
        self.mut_reg_bits(TCSR1_OF, TCSR_UDT | TCSR_ARHT, TCSR_CASC | TCSR_GENT)

        self._write(TLR0_OF, self.max_count)
        self._write(TLR1_OF, int(self.max_count * duty_cycle_percent))

        self.mut_reg_bits(TCSR0_OF, 0, TCSR_CAPT)
        self.mut_reg_bits(TCSR1_OF, 0, TCSR_CAPT)


    def start(self):
        self.mut_reg_bits(TCSR0_OF, TCSR_PWMA | TCSR_GENT, 0)
        self.mut_reg_bits(TCSR1_OF, TCSR_PWMA | TCSR_GENT, 0)

        self.reset_counts()

        # Set enable all bit
        self.mut_reg_bits(TCSR0_OF, TCSR_ENALL, 0)

    def stop(self):
        self.mut_reg_bits(TCSR0_OF, 0, TCSR_ENT)
        self.mut_reg_bits(TCSR1_OF, 0, TCSR_ENT)

    def reset_counts(self):
        self.mut_reg_bits(TCSR0_OF, TCSR_LOAD, 0)
        self.mut_reg_bits(TCSR0_OF, 0, TCSR_LOAD)

        self.mut_reg_bits(TCSR1_OF, TCSR_LOAD, 0)
        self.mut_reg_bits(TCSR1_OF, 0, TCSR_LOAD)

    def mut_reg_bits(self, offset, set_mask, unset_mask):
        reg = self._read(offset)
        reg = _set(reg, set_mask)
        reg = _unset(reg, unset_mask)
        self._write(offset, reg)

    def _read(self, offset):
        if self.debug:
            print("Reading offset {}".format(offset))

        return self.drv.read(offset)

    def _write(self, offset, value):
        if self.debug:
            print("Writing {} to offset {}".format(value, offset))

        return self.drv.write(offset, value)

if __name__ == '__main__':
    overlay = Overlay('../bit/kv260_fanctrl.bit')
    pwm = AxiPwmCtrl(overlay.fan_pwm_ctrl, debug=True)

    # Briefly set the fan to a high speed  to overcome stall
    pwm.configure(0.0)
    pwm.start()

    time.sleep(1)

    # Set to 75% duty. Experimentally 70-75% is needed
    # to keep the fan spinning at all, so the fan won't
    # be "quiet"
    pwm.configure(0.25)
    pwm.start()
