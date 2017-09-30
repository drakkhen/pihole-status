#!/usr/bin/env python
# -*- coding: utf-8 -*-

from adafruitdisplay import *

import json
import requests
import subprocess
import time

class PiholeDisplayController:
    def __init__(self, api_url='http://localhost/admin/api.php'):
        self.api_url = api_url
        self.ada_display = AdaFruitDisplay()

        self.data = None
        self.last_data = None

        self.pihole_status_frame = TextFrame(self.ada_display)
        self.pihole_ads_blocked_frame = TextFrame(self.ada_display)
        self.os_status_frame = OsStatusFrame(self.ada_display)

        font_path = os.path.join(font_dir(), 'slkscr.ttf')
        self.pihole_ads_blocked_frame.set_font(font_path, 8 * 4)
        self.pihole_ads_blocked_frame.top = -6

    def update_pihole_data(self):
        r = requests.get(self.api_url)

        self.last_data = self.data
        self.data = json.loads(r.text)

        return cmp(self.last_data, self.data) != 0

    def show_pihole_status(self):
        ip_addr = self.shell("hostname -I | cut -d\' \' -f1").rstrip()
        hostname = self.shell("hostname -s").rstrip()

        self.pihole_status_frame.clear()
        self.pihole_status_frame.add_line("IP: %s (%s)" % (ip_addr, hostname))
        self.pihole_status_frame.add_line("Blocked:  %d  (%.2f%%)" % (self.data['ads_blocked_today'], self.data['ads_percentage_today']))
        self.pihole_status_frame.add_line("Queries:   %d" % self.data['dns_queries_today'])
        self.pihole_status_frame.add_line("Clients:   %d" % self.data['unique_clients'])
        self.ada_display.display_frame(self.pihole_status_frame)

    def show_ads_blocked(self):
        self.pihole_ads_blocked_frame.clear("white")
        self.pihole_ads_blocked_frame.center_text(str(self.data['ads_blocked_today']), "black")
        self.ada_display.display_frame(self.pihole_ads_blocked_frame)

    def show_os_status(self):
        self.os_status_frame.update()
        self.ada_display.display_frame(self.os_status_frame)

    def shell(self, cmd):
        res = subprocess.check_output(cmd, shell=True)
        return res

    def go(self):
        while True:
            updated = self.update_pihole_data()

            sleep = 0.5

            new = 0
            if self.last_data:
                new = self.data['ads_blocked_today'] - self.last_data['ads_blocked_today']

            if new > 0:
                self.data['ads_blocked_today'] = self.last_data['ads_blocked_today'] + 1
                self.show_ads_blocked()

                if new > 1:
                    sleep = 0.1

            elif int(time.time() % 10 >= 5):
                self.show_os_status()

            else:
                self.show_pihole_status()

            time.sleep(sleep)


if __name__ == '__main__':
    controller = PiholeDisplayController()
    controller.go()
