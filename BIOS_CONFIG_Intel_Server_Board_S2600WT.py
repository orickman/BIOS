import pexpect
import sys
import time

'''
This script is to automatically configure PXE boot for Intel Server Board S2600WT Family.
'''

term_srv = sys.argv[1]
port = sys.argv[2]
boot_dev1 = sys.argv[3]
boot_dev2 = sys.argv[4]
boot_dev3 = sys.argv[5]
model = sys.argv[6]

port = int(port) + 2000

timeout = 900
idle = 5 # time wait between menu refresh

telnet_session = 'telnet ' + term_srv + ' ' + str(port)
exp = pexpect.spawn(telnet_session, timeout=timeout)

# Keystoke definition

keys = {
    'UP':'\x1B[A',
    'DOWN':'\x1B[B',
    'ENTER': '\r\n',
    'F2': "\x1BOQ",
    'F9': "\x1B[20~",
    'F10': "\x1B[21~",
    'F12': "\x1B[24~",
    'ESCAPE': '\x1B',
    'MINUS': '-',
    'PLUS': '+'
}

# http://pueblo.sourceforge.net/doc/manual/ansi_color_codes.html
# https://en.wikipedia.org/wiki/ANSI_escape_code#Escape_sequences
# Code: Client: Meaning:
# [0m           reset; clears all colors and styles (to white on black)
# [1m    --     bold on
# [30m   --     set foreground color to black
# [37m   --     set foreground color to white
# [40m   --     set background color to black
# [44m   --     set background color to blue
# [46m   --     set background color to cyan
# [47m   --     set background color to white


# To fully match the exact target menu from a character console,
# we have to use the exact menu match including ASNI colors in the regex.
# For example, to match the highlighted "Main" menu, the fully consturctred regex
# menu_highlight_begin + 'Main' + menu_highlight_end
# has to be used.

menu_highlight_begin = '.\[0m.\[37m.\[40m.\[\d+;\d+H'
menu_highlight_end   = '.\[0m.\[30m.\[47m'
pop_highlight_begin  = '.\[1m.\[37m.\[46m.\[\d+;\d+H'
pop_highlight_end    = '.\[0m.\[37m.\[44m'

setup_menu =  menu_highlight_begin + 'Setup Menu' + menu_highlight_end
main_menu  =  menu_highlight_begin + 'Main' + menu_highlight_end

def go_to(pattern=None, direction=keys['DOWN']):
    not_found = 1
    tries = 0
    limit = 10

    while not_found != 0 and tries < limit:
        not_found = exp.expect([pattern, pexpect.TIMEOUT], timeout=5)
        if not_found == 1:
            exp.sendline(direction)
        tries += 1
        print("\n>>>DBG:  {} tries DOWN \n".format(tries))

    print("\n>>>DBG: Took {} {} tries to reach the menu {}\n".format(tries, direction, pattern))
    if not_found == 1:
        return 1
    return 0

def enable_pxe():

    # Setting PXE on PRIMARY

    print ("\n>>>ENABLING PXE\n")

    if go_to(menu_highlight_begin + 'Advanced' + menu_highlight_end) != 0:
        print ("\n>>>Cannot find Advanced menu\n")
        exit(1)

    exp.sendline(keys['ENTER'])
    print ("\n>>>In Advanced sub-menu\n")

    if go_to(menu_highlight_begin + 'PCI Configuration' + menu_highlight_end) != 0:
        print ("\n>>>Cannot find PCI Configuration menu\n")
        exit(1)

    print ("\n>>>Entering PCI Configuration\n")
    exp.sendline(keys['ENTER'])
    print ("\n>>>In PCI Configuration sub-menu\n")


    if go_to(menu_highlight_begin + 'NIC Configuration' + menu_highlight_end) != 0:
        print ("\n>>>Cannot find NIC Configuration menu\n")
        exit(1)

    print ("\n>>>Entering NIC Configuration\n")
    exp.sendline(keys['ENTER'])
    print ("\n>>>In NIC Configuration sub-menu\n")

    if go_to(menu_highlight_begin + '<(?:Disabled|Enabled)>' + menu_highlight_end + '.*' + 'PXE 10GbE Option ROM') != 0:
        print ("\n>>>Cannot find PXE 10GbE Option ROM\n")
        exit(1)

    exp.sendline(keys['ENTER'])
    print("\n>>>Entering PXE 10GbE Option ROM\n")

    # rom_pxe_status is an index number: 0 - Enabled, 1 - Disabled
    try:
        rom_pxe_status = exp.expect([pop_highlight_begin+'Enabled', pop_highlight_begin+'Disabled'])
        if rom_pxe_status == 0:
            print ("\n>>>ROM PXE already enabled, escape\n")
            exp.sendline(keys['ESCAPE'])
        elif rom_pxe_status == 1:
            print ("\n>>>Enabling ROM PXE...\n")
            exp.sendline(keys['UP'])
            exp.sendline(keys['ENTER'])
            print ("\n>>>ROM PXE Enabled\n")
    except pexpect.TIMEOUT:
        print("\nCould not determine if PXE 10GbE ROM was enabled\n")
        exit(1)

    print("\n>>>Enabled PXE 10GbE Option ROM\n")

    if go_to(menu_highlight_begin + '<(?:Disabled|Enabled)>' + menu_highlight_end +'.\[\d+;\d+H\s+.\[\d+;\d+H\s+.\[\d+;\d+H'+'NIC1 Port1 PXE') != 0:
        print ("\n>>>Cannot find NIC1 Port1 PXE\n")
        exit(1)

    print ("\n>>>Entering NIC1 Port1 PXE\n")
    exp.sendline(keys['ENTER'])

    # nic1_p1_pxe_status is an index number: 0 - Enable 1 - Disable
    try:
        nic1_p1_pxe_status = exp.expect([pop_highlight_begin+'Enabled', pop_highlight_begin+'Disabled'])
        if nic1_p1_pxe_status == 0:
            print ("\n>>>NIC1 Port1 PXE already enabled, escape\n")
            exp.sendline(keys['ESCAPE'])
        elif nic1_p1_pxe_status == 1:
            print ("\n>>>Enabling PXE...\n")
            exp.sendline(keys['UP'])
            exp.sendline(keys['ENTER'])
            print ("\n>>>PXE Enabled\n")
    except pexpect.TIMEOUT:
        print("\nCould not determine if NIC1 Port1 was PXE enabled\n")
        exit(1)

    print("\n>>>Enabled NIC1 Port1 PXE\n")

    print("\n>>>Saving and Exiting..\n")

    # F10 to save and exit
    exp.sendline(keys['F10'])
    time.sleep(idle)
    exp.sendline("y\n")

def set_boot_priority():

    # Setting PRIMARY as first boot option

    print ("\n>>>SETTING BOOT PRIORITY\n")

    saw_boot_prompt = 0

    index = 0

    while index != 5:
        # Expect any of these five patterns during BIOS booting.
        # ['\[F2\]', 'Press any key to continue', 'Setup Menu', 'Main', 'boot:']

        try:
            index = exp.expect(['\[F2\]', 'Press any key to continue', setup_menu, main_menu, 'boot:', pexpect.TIMEOUT],timeout=timeout)

            if index == 0:
                print("\n>>>F2 matched\n")
                exp.sendline(keys['F2'])
                print("\n>>>F2 pressed to enter BIOS\n")

            elif index == 1:
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to skip BIOS warning\n")

            elif index == 2:
                print("\n>>>Setup Menu matched\n")
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to enter Setup Menu\n")

            elif index == 3:
                print("\n>>>Already in BIOS window - Main Menu\n")
                print("\n>>>Matching highlighted Boot Maintenance Manager menu\n")
                if go_to(menu_highlight_begin + 'Boot Maintenance Manager') != 0:
                    print("\n>>>Did not see Boot Maintenance Manager Menu\n")
                    exit(1)
                exp.sendline(keys['ENTER'])
                print ("\n>>>In Boot Maintenance Manager sub-menu\n")
                break

            elif index == 4:
                print ("\n>>>Saw PXE boot prompt. Exiting...\n")
                saw_boot_prompt = 1
                return 1

        except pexpect.TIMEOUT:
            print ("\n>>>Didn't see anything interesting from console, the unit does not look like have power on\n")
            exp.close(force=True)
            exit(1)

    if saw_boot_prompt:
        return ''

    if go_to(menu_highlight_begin + 'Legacy Network Device Order' + menu_highlight_end) != 0:
        print ("\n>>>Cannot find Network Device Order option\n")
        exp.sendline(keys['ESCAPE'])
        exp.sendline(keys['DOWN'])
        time.sleep(idle)
        return 0

    print ("\n>>>Found Legacy Network Device Order\n")
    exp.sendline(keys['DOWN'])

    if go_to(menu_highlight_begin + 'Change Boot Order' + menu_highlight_end) != 0:
        print("Did not find Change Boot Order\n")
        exit(1)
    print ("\n>>>Found Change Boot Order\n")

    print ("\n>>>Entering Change Boot Order\n")
    exp.sendline(keys['ENTER'])

    print ("\n>>>Another Enter to get the boot order pop-up menu\n")
    exp.sendline(keys['ENTER'])

    # Select PRIMARY port as boot device
    if go_to(pop_highlight_begin+'IBA XE Slot \d+00 v\d+') != 0:
        print ("\nFailed to enable NIC slot0 as primary boot device\n")
        return 0
    else:
        exp.sendline(keys['PLUS'])
        exp.sendline(keys['PLUS'])
        exp.sendline(keys['ENTER'])
        print ("\n>>>Enabled IBA GE Slot0 as primary boot device\n")

    # F10 to save and exit
    exp.sendline(keys['F10'])
    time.sleep(idle)
    exp.sendline("y\n")
    return 1

def set_boot_from_hdd():

    # Setting HDD as first boot option

    print ("\n>>>SETTING BOOT FROM DISK\n")

    saw_boot_prompt = 0

    index = 0
    while index != 5:
        # Expect any of these five patterns during BIOS booting.
        # ['\[F2\]', 'Press any key to continue', 'Setup Menu', 'Main', 'boot:']
        try:
            index = exp.expect(['\[F2\]', 'Press any key to continue', setup_menu, main_menu, 'boot:', pexpect.TIMEOUT],timeout=timeout)

            if index == 0:
                print("\n>>>F2 matched\n")
                exp.sendline(keys['F2'])
                print("\n>>>F2 pressed to enter BIOS\n")

            elif index == 1:
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to skip BIOS warning\n")

            elif index == 2:
                print("\n>>>Setup Menu matched\n")
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to enter Setup Menu\n")

            elif index == 3:
                print("\n>>>Already in BIOS window - Main Menu\n")
                print("\n>>>Matching highlighted Advanced menu\n")
                rc = go_to(menu_highlight_begin + 'Advanced' + menu_highlight_end)
                if rc !=0:
                    print("\n>>>Did not see Advanced Menu\n")
                    exit(1)
                exp.sendline(keys['ENTER'])
                print("\nENTER key preessed\n")
                print ("\n>>>In Advanced sub-menu\n")
                break

            elif index == 4:
                print ("\n>>>Saw PXE boot prompt. Exiting...\n")
                saw_boot_prompt = 1
                return 1

        except pexpect.TIMEOUT:
            print ("\n>>>Didn't see anything interesting from console, the unit does not look like have power on\n")
            #patten_matched = 0
            exp.close(force=True)
            exit(1)

    if saw_boot_prompt:
        print("The unit booted up too fast onto the PXE prompt. Exiting and retrying...\n")
        exit(1)

    print("\n>>>DISABLING PXE\n")

    if go_to(menu_highlight_begin + 'PCI Configuration' + menu_highlight_end) != 0:
        print ("\n>>>Cannot find PCI Configuration menu\n")
        exit(1)

    print ("\n>>>Entering PCI Configuration\n")
    exp.sendline(keys['ENTER'])
    print ("\n>>>In PCI Configuration sub-menu\n")


    if go_to(menu_highlight_begin + 'NIC Configuration' + menu_highlight_end) != 0:
        print ("\n>>>Cannot find NIC Configuration menu\n")
        exit(1)

    print ("\n>>>Entering NIC Configuration\n")
    exp.sendline(keys['ENTER'])
    print ("\n>>>In NIC Configuration sub-menu\n")

    if go_to(menu_highlight_begin + '<(?:Disabled|Enabled)>' + menu_highlight_end + '.*' + 'PXE 10GbE Option ROM') != 0:
        print ("\n>>>Cannot find PXE 10GbE Option ROM\n")
        exit(1)

    exp.sendline(keys['ENTER'])
    print("\n>>>Entering PXE 10GbE Option ROM\n")

    # rom_pxe_status: 0 - Enabled 1 - Disabled
    try:
        rom_pxe_status = exp.expect([pop_highlight_begin+'Enabled', pop_highlight_begin+'Disabled'])
        if rom_pxe_status == 0:
            print ("\n>>>Disabling ROM PXE...\n")
            exp.sendline(keys['DOWN'])
            exp.sendline(keys['ENTER'])
            print ("\n>>>ROM PXE Disabled\n")

        elif rom_pxe_status == 1:
            print ("\n>>>ROM PXE Already disabled\n")
            exp.sendline(keys['ESCAPE'])

    except pexpect.TIMEOUT:
        print("\nCould not determine if PXE 10GbE ROM was disabled\n")
        exit(1)

    print("\n>>>Disabled PXE 10GbE Option ROM\n")

    # Go back to Boot Maintenance Manager menu
    exp.sendline(keys['ESCAPE'])
    exp.sendline(keys['ESCAPE'])
    exp.sendline(keys['ESCAPE'])
    exp.sendline(keys['UP'])

    if go_to(menu_highlight_begin + 'Boot Maintenance Manager' + menu_highlight_end) != 0:
        print("\n>>>Did not see Boot Maintenance Manager Menu\n")
        exit(1)
    exp.sendline(keys['ENTER'])
    print ("\n>>>In Boot Maintenance Manager sub-menu\n")

    if go_to(menu_highlight_begin + 'Change Boot Order' + menu_highlight_end) != 0:
        print("Did not find Change Boot Order\n")
        exit(1)

    print ("\n>>>Entering Change Boot Order\n")
    exp.sendline(keys['ENTER'])

    print ("\n>>>Another Enter to get the boot order pop-up menu\n")
    exp.sendline(keys['ENTER'])

    # Set HDD port as boot device
    if go_to(pop_highlight_begin + '\(SATA\)') != 0:
        print ("\nFailed to enable boot from HDD\n")
        return 0
    else:
        exp.sendline(keys['PLUS'])
        exp.sendline(keys['PLUS'])
        exp.sendline(keys['ENTER'])
        print ("\n>>>Enabled HDD as primary boot device\n")

    # F10 to save and exit
    exp.sendline(keys['F10'])
    time.sleep(idle)
    exp.sendline("y\n")
    return 1

def boot_from_net():
    # Boot directly from PRIMARY

    print ("\n>>>BOOT DIREDTLY FROM NET\n")
    saw_boot_prompt = 0
    index = 0

    while index != 5:
        # We expect any of these five patterns during BIOS booting.
        # ['\[F2\]', 'Press any key to continue', 'Setup Menu', 'Main', 'boot:']

        try:
            index = exp.expect(['\[F2\]', 'Press any key to continue', setup_menu, main_menu, 'boot:', pexpect.TIMEOUT], timeout=timeout)

            if index == 0:
                print("\n>>>F2 matched\n")
                exp.sendline(keys['F2'])
                print("\n>>>F2 pressed to enter BIOS\n")

            elif index == 1:
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to skip BIOS warning\n")

            elif index == 2:
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to Setup menu - BIOS\n")

            elif index == 3:
                print ("\n>>>Already in BIOS window - Setup Menu\n")
                print("\n>>> Matching highlighted Boot Manager menu\n")
                if go_to(menu_highlight_begin + 'Boot Manager') != 0:
                    print("\n>>>Did not see Boot Manager Menu\n")
                    exit(1)
                exp.sendline(keys['ENTER'])
                print ("\n>>>In Boot Manager sub-menu\n")
                break

            elif index == 4:
                print ("\n>>>Saw PXE boot prompt. Exiting...\n")
                saw_boot_prompt = 1
                return 1

        except pexpect.TIMEOUT:
            print ("\n>>>Didn't see anything interesting from console, the unit does not look like have power on\n")
            exp.close(force=True)
            exit(1)

    if saw_boot_prompt:
        return ''

    if go_to(menu_highlight_begin+'IBA XE Slot \d+00 v\d+') == 0:

        exp.sendline(keys['ENTER'])
        print("\n>>>Selected to boot from IBA XE Slot0\n")
        time.sleep(idle)

        matched_index = exp.expect([main_menu, 'boot:'], timeout=5)

        if matched_index == 0:
            print("\n>>>Looks like we are back to Main Menu after press boot from IBA XE Slot0, need to call enable_pxe\n")
            return 0
        elif matched_index == 1:
            print("\n>>> Booting directly from network\n")
            return 1
    else:
        print("\n>>>Cannot find primary device. Need to enable primary to PXE boot\n")
        exp.sendline(keys['ESCAPE'])
        exp.sendline(keys['DOWN'])
        return 0

def load_defaults():

    print ("\n>>>LOADING SETUP DEFAULTS\n")

    index = 0

    while index != 5:
        # We expect any of these five patterns during BIOS booting.
        # ['\[F2\]', 'Press any key to continue', 'Setup Menu', 'Main', 'boot:']

        try:
            index = exp.expect(['\[F2\]', 'Press any key to continue', setup_menu, main_menu, 'boot:', pexpect.TIMEOUT],timeout=timeout)

            if index == 0:
                print("\n>>>F2 matched\n")
                exp.sendline(keys['F2'])
                print("\n>>>F2 pressed to enter BIOS\n")

            elif index == 1:
                exp.sendline(keys['ENTER'])
                print ("\n>>>Enter key pressed to skip BIOS warning\n")

            elif index == 2 or index == 3:
                print ("\n>>>Already in BIOS\n")

                # F9 to load defaults
                exp.sendline(keys['F9'])
                time.sleep(idle)
                exp.sendline("y\n")
                print ("\n>>>Loaded Setup Defaults\n")
                time.sleep(idle)

                # F10 to save and exit
                exp.sendline(keys['F10'])
                time.sleep(idle)
                exp.sendline("y\n")
                print ("\n>>>Saved configuration and exit\n")
                return 0

            elif index == 4:
                print ("\n>>>Saw PXE boot prompt. Exiting...\n")
                saw_boot_prompt = 1
                return 1

        except pexpect.TIMEOUT:
            print ("\n>>>Didn't see anything interesting from console, the unit does not look like have power on\n")
            #patten_matched = 0
            exp.close(force=True)
            exit(1)

    # F9 to load defaults
    exp.sendline(keys['F9'])
    time.sleep(idle)
    exp.sendline("y\n")
    print ("\n>>>Loaded Setup Defaults\n")

    # F10 to save and exit
    exp.sendline(keys['F10'])
    time.sleep(idle)
    exp.sendline("y\n")
    print ("\n>>>Saved configuration and exit\n")


if __name__ == '__main__':

    if boot_dev1 == '4' or boot_dev1 == '5' or boot_dev1 == '6':
        try:
            load_defaults()
        except Exception as e:
            print("Failed to load defauts")

    if boot_dev1 == '2':
        try:
            rv = set_boot_priority()
            if rv != 1:
                enable_pxe()
                set_boot_priority()
        except Exception as e:
            print("Failed to set boot from primay")

    if boot_dev1 == '8':
        try:
            rv = boot_from_net()
            if rv != 1:
                enable_pxe()
                boot_from_net()
        except Exception as e:
            print("Failed to set boot from net")

    exp.close(force=True)

    print("\n>>>EXITING BIOS...\n")

## Unit test:

# python3 biosboot_pike.py  10.34.64.126 14 4 4 4 gx10000
# python3 biosboot_pike.py  10.34.64.126 14 2 4 4 gx10000
# python3 biosboot_pike.py  10.34.64.126 14 8 4 4 gx10000
