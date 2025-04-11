"""
Low-level python driver for MUX2001 REVA cards

This driver creates the basic SPI output data given card and channel selections
GPIO and actually writing the SPI data must be configured in the application code according to available hardware

Organazation:
    Stack:  
        All cards that are dasiy-chained on the same SPI bus.
        All share common D_CLK and nMR signals.

    Card Group:
        Group of cards working in parallel
        All cards in a group share a SUM_CMD_DMM and R_CLK signals
        All cards in a group are cleared at the same time
        Only one channel total is allowed to be active in a group
        1-indexed for arguments to line up with schematic/PCB labeling
            Given N groups:
            group 1 is the group farthest from the SPI controller, since it receives the first bytes written
            group N is the group closest to the SPI controller, since it receives the last bytes written
        card group indexing is converted to 0 indexed within the class methods to line up with SPI data buffers
        
        
    Card:
        Single physical card
        Has 20 voltage channels, a COM channel, and 1 current channel
        1-indexed for arguments to line up schematic/PCB labeling
            Given N cards in a group:
            card 1 is the card farthest from the SPI controller, since it receives the first bytes written
            card N is the card closest tot he SPI controller, since it receives the last bytes written
        card indexing is converted to 0 indexed within the class methods to line up with SPI data buffers
        
    Channel:
        Each card has channels 0 through 21
        ch0 is the common channel, (V_CH_COM on the schematic)
        ch1-20 are the voltage channels, V_CH_1 through V_CH_20 on the schematic
        ch21 is the current channel, I_CH_21+ and I_CH_21- combined on the schematic
        channels are referenced by tuples (group, card, in_p, in_n)
            group is the 1-indexed group
            card is the 1-indexed card with respect to the group
                i.e. (group=1, card=1) is not the same card as (group=2, card=1)
                card numbering resets for each group, every group has its own card #1
            in_p is the positive input pin
                can be CH1 - CH20 when using CH0 (V_CH_COM) as in_n
                must be an odd numbered channel when doing 2-pole differential measurements
            in_n is the negative input pin
                can be CH0 for single-ended measurements with respect to V_CH_COM
                must be (in_p + 1) when doing 2-pole differential measurements
        examples:
            MUX_DMM_VCC = (1, 1, 5, 0)  # group 1, card 1, channel 5 single-ended
            MUX_DMM_VCC_SHUNT = (1, 1, 5, 6)  # group 1, card 1, channel 5 to 6 differential measurement
            
            mux.set_ch(MUX_DMM_VCC)
            vcc_voltage = dmm.measure_vdc()
            mux.set_ch(MUX_DMM_VCC_SHUNT)
            vcc_current = dmm.measure_vdc() / 0.001
            
        

"""

import time

class MuxStack:
    def __init__(self, read_nmr_fn, write_spi_bytes_fn):
        self.read_nmr = read_nmr_fn  # nMR GPIO read function
        self.write_spi_bytes = write_spi_bytes_fn  # Write SPI data bytes function

        #  Create empty list of cards
        self._card_groups = []
        
    def add_card_group(self, num_cards, write_rclk_fn):
        self._card_groups.append(self.MuxCardGroup(num_cards, write_rclk_fn))        
        
    # clear all card data and outputs
    def clear_all(self):
        for i in range(len(self._card_groups)):  # clear each card and pack SPI buffer
            self._card_groups[i].clear()
        return self._write_spi()        
        
    # clear single card (group and card arguments are 1 indexed)
    def clear_group(self, group):
        i = group - 1
        self._card_groups[i].clear()
        return self._write_spi()
        
    # select output channel
    def set_ch(self, ch_tuple):
        group = ch_tuple[0] - 1
        card = ch_tuple[1] - 1
        in_p = ch_tuple[2]
        in_n = ch_tuple[3]
        
        self._card_groups[group].set_ch(card, in_p, in_n)
        
        self._write_spi()
    
    # write all cards with their current spi data
    def _write_spi(self):
        self.spi_data = []  # clear spi data buffer
        for i in range(len(self._card_groups)):  # clear each card group
            self.spi_data.extend(self._card_groups[i].spi_data)
            self._card_groups[i].write_rclk(0)  # set all R_CLK signals low
            
        time.sleep(0.04)  # required timing delay
        self.write_spi_bytes(self.spi_data)  # write SPI data        
        
        for i in range(len(self._card_groups)):  # clear each card and pack SPI buffer
            self._card_groups[i].write_rclk(1)  # set all R_CLK signals high
        
        time.sleep(0.005)  # give relays time to close.  Recommended, but not required
            
        if(self.read_nmr()):  # check nMR state
            return 1
        else: return 0
    
    class MuxCardGroup:
        def __init__(self, num_cards, write_rclk_fn):
            self.num_cards = num_cards
            self.write_rclk_fn = write_rclk_fn
            self.spi_data = [0] * 3 * num_cards
            self.cards = []
            for i in range(num_cards):
                self.cards.append(self.MuxCard())
        
        def write_rclk(self, state):
            self.write_rclk_fn(state)
            
        def clear(self):
            self.spi_data = []
            for i in range(self.num_cards):
                self.cards[i].clear()
                self.spi_data.extend(self.cards[i].spi_data)
                
        def set_ch(self, card, in_p, in_n):
            self.clear()
            self.cards[card].set_ch(in_p, in_n)
            self.spi_data = []
            for i in range(self.num_cards):
                self.spi_data.extend(self.cards[i].spi_data)
        
        class MuxCard:
            def __init__(self):
                self.spi_data = [0, 0, 0] 
                self.lut = [0x80, 0x40, 0x10, 0x08, 0x04]
                
            def clear(self):
                self.spi_data = [0, 0, 0]
            
            def set_ch(self, in_p, in_n):
                self.clear()
                if in_p == 21:  # current channel
                    self.spi_data[1] = 0x02

                elif (in_p % 2 == 1) and (in_n == in_p + 1) and (1 <= in_p <= 19):   # 2-pole measurement
                    self.spi_data[2] = 0x10  # set AB_TO_VCOM                    
                    if 1 <= in_p <= 10:
                        self.spi_data[0] = self.lut[int((in_p - 1)/2)]                    
                    elif 11 <= in_p <= 19:
                        self.spi_data[1] = self.lut[int((in_p - 11)/2)]  

                elif in_n == 0 and (1 <= in_p <= 20):    # Single-ended measurement
                    if (in_p % 2) == 1:
                        self.spi_data[2] = 0x08  # if odd channel, select A_TO_V
                    else:
                        self.spi_data[2] = 0x04  # if even channel, select B_TO_V

                    if 1 <= in_p <= 10:
                        self.spi_data[0] = self.lut[int((in_p - 1)/2)]  
                    elif 11 <= in_p <= 20:
                        self.spi_data[1] = self.lut[int((in_p - 11)/2)]
        
        