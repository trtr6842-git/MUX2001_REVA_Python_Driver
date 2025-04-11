from labjack import ljm
import time
from MUX2001_REVA import *

# Connect to Labjack
print('\nStarting MUX2001 test with Labjack as IO controller')
print('Connecting to Labjack...')
labjack = ljm.openS("T4", "ANY", "ANY")  # open the test labjack via any method
info = ljm.getHandleInfo(labjack)  # get labjack connection info
print('LabJack T%i SN%i connected\n' % (info[0], info[2]))  # print info

# Configure Labjack SPI and GPIO
# https://en.wikipedia.org/wiki/Serial_Peripheral_Interface
# CPOL = 0
# CPHA = 0

ljm.eWriteName(labjack, 'CIO0', 0)  # set CLK default low REQUIRED
ljm.eWriteName(labjack, 'SPI_CLK_DIONUM', 16)  # CIO0 as SPI CLK: D_CLK on MUX2001
ljm.eWriteName(labjack, 'SPI_MOSI_DIONUM', 17)  # CIO1 as MOSI: D_IN on MUX2001
ljm.eWriteName(labjack, 'SPI_MODE', 0)
ljm.eWriteName(labjack, 'SPI_OPTIONS', 1)
ljm.eWriteName(labjack, 'SPI_SPEED_THROTTLE', 65500)  # 100kHz SPI clock


# SPI and GPIO pin abstraction functions to pass to MUX class
# Re-write these to adapt to Raspberry Pi or other controllers

def write_rclk_gpio(state):
    # write R_CLK signal output state (0=low, 1=high)
    # Low for clears card(s) immediately
    # rising edge after ≥40ms low time clocks in data
    # R_CLK is used somewhat similarly to a SPI nCS signal, but does not disable data/clock inputs when high
    
    # implement your GPIO write with appropriate R_CLK pin here:
    ljm.eWriteName(labjack, 'CIO2', bool(state))  # labjack CIO2 used as R_CLK signal
    
def read_nmr_gpio():
    # read and return nMR signal input state  
    # High = OK, low = FAULT
    # nMR is an open-drain signal with a weak (~100k) pullup resistor to VCC per card
    # nMR can aslo be pulled low externally to reset all MUX cards in a stack
    
    # Implement your GPIO read with appropriate nMR pin here:
    return ljm.eReadName(labjack, 'CIO3')  # labjack CIO3 used as nMR input signal

def write_spi_bytes(spi_data_bytes):
    # argument is list of SPI data bytes from MUX2001_REVA class
    # implement whatever is needed to sequentially write all SPI bytes starting with element at index 0
    
    # implement your SPI write function here:
    num_bytes = len(spi_data_bytes)
    ljm.eWriteName(labjack, 'SPI_NUM_BYTES', num_bytes)
    ljm.eWriteNameByteArray(labjack, 'SPI_DATA_TX', num_bytes, spi_data_bytes)
    ljm.eWriteName(labjack, 'SPI_GO', 1)
    
NUM_MUX_CARDS = 10  # define number of cards in stack
mux = MuxStack(read_nmr_gpio, write_spi_bytes) # initialize mux stack class
mux.add_card_group(NUM_MUX_CARDS, write_rclk_gpio)  # add one group of 10 parallel cards
mux.clear_all()  # clear all cards in all groups

for card in range(10):
    for ch in range(20):
        mux.set_ch((1, card+1, ch+1, 0))
        time.sleep(0.05)

mux.clear_all()
time.sleep(0.5)
        
for card in range(10):
    for ch in range(20):
        if((ch+1) % 2 == 1):
            mux.set_ch((1, card+1, ch+1, ch+2))
            time.sleep(0.05)
            
mux.clear_all()
time.sleep(0.5)

for card in range(10):
    mux.set_ch((1, card+1, 21, 21))
    time.sleep(0.05)
    
time.sleep(0.5)
mux.clear_all()  # clear all cards in all groups
    
            






