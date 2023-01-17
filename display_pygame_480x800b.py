#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: This library supports using pygame 
 on your Linux development PC for debug and development 
 purposes. Only works in a graphical desktop 
 environment.  Tested on Ubuntu 20.04.  

 This version supports arrow keys (up/down) and enter.  

*****************************************
'''

'''
 Imported Libraries
'''
import time
import threading
import socket
import pygame 
from display_base_480x800 import DisplayBase
from gpiozero import Button

'''
Display class definition
'''
class Display(DisplayBase):

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		super().__init__(dev_pins, buttonslevel, rotation, units)

	def _init_display_device(self):
		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _init_input(self):
		self.input_enabled = True
		self.input_event = None
		# Init Menu Structures
		self._init_menu()
		# Init GPIO for button input, setup callbacks: Uncomment to utilize GPIO input
		self.up = self.dev_pins['input']['up_clk'] 		# UP - GPIO16
		self.down = self.dev_pins['input']['down_dt']	# DOWN - GPIO20
		self.enter = self.dev_pins['input']['enter_sw'] # ENTER - GPIO21
		self.debounce_ms = 500  # number of milliseconds to debounce input
		self.input_event = None
		self.input_counter = 0

		# ==== Buttons Setup =====
		self.pull_up = self.buttonslevel == 'HIGH'

		self.up_button = Button(pin=self.up, pull_up=self.pull_up, hold_time=0.25, hold_repeat=True)
		self.down_button = Button(pin=self.down, pull_up=self.pull_up, hold_time=0.25, hold_repeat=True)
		self.enter_button = Button(pin=self.enter, pull_up=self.pull_up)

		# Init Menu Structures
		self._init_menu()
		
		self.up_button.when_pressed = self._up_callback
		self.down_button.when_pressed = self._down_callback
		self.enter_button.when_pressed = self._enter_callback
		self.up_button.when_held = self._up_callback
		self.down_button.when_held = self._down_callback

	'''
	============== Input Callbacks ============= 
	'''
	def _enter_callback(self):
		self.input_event='ENTER'

	def _up_callback(self, held=False):
		self.input_event='UP'

	def _down_callback(self, held=False):
		self.input_event='DOWN'

	def _display_loop(self):
		"""
		Main display loop
		"""
		# Init Device
		pygame.init()
		# set the pygame window name 
		pygame.display.set_caption('PiFire Device Display')
		# Create Display Surface
		self.display_surface = pygame.display.set_mode(size=(self.WIDTH, self.HEIGHT), flags=pygame.FULLSCREEN)
		self.display_command = 'splash'

		while True:			
			''' Normal display loop'''
			self._event_detect()

			if self.display_timeout:
				if time.time() > self.display_timeout:
					self.display_timeout = None
					if not self.display_active:
						self.display_command = 'clear'

			if self.display_command == 'clear':
				self.display_active = False
				self.display_timeout = None
				self.display_command = None
				self._display_clear()

			if self.display_command == 'splash':
				self._display_splash()
				self.display_timeout = time.time() + 3
				self.display_command = 'clear'
				pygame.time.delay(3000) # Hold splash screen for 3 seconds

			if self.display_command == 'text':
				self._display_text()
				self.display_command = None
				self.display_timeout = time.time() + 10

			if self.display_command == 'network':
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				s.connect(("8.8.8.8", 80))
				network_ip = s.getsockname()[0]
				if network_ip != '':
					self._display_network(network_ip)
					self.display_timeout = time.time() + 30
					self.display_command = None
				else:
					self.display_text("No IP Found")

			if self.menu_active and not self.display_timeout:
				if time.time() - self.menu_time > 5:
					self.menu_active = False
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					if not self.display_active:
						self.display_command = 'clear'
			elif not self.display_timeout and self.display_active:
				if self.in_data is not None and self.status_data is not None:
					self._display_current(self.in_data, self.status_data)

		pygame.quit()

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _display_clear(self):
		print(f'[{time.time()}]  Screen Cleared.')
		self.display_surface.fill((0,0,0))
		pygame.display.update() 

	def _display_canvas(self, canvas):
		# Convert to PyGame and Display
		strFormat = canvas.mode
		size = canvas.size
		raw_str = canvas.tobytes("raw", strFormat)
		
		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 

	'''
	 ====================== Input & Menu Code ========================
	'''
	def _event_detect(self):
		"""
		Called to detect input events from buttons, encoder, touch, etc.
		"""
		command = self.input_event  # Save to variable to prevent spurious changes 
		if command:
			self.display_timeout = None  # If something is being displayed i.e. text, network, splash then override this

			if command not in ['UP', 'DOWN', 'ENTER']:
				return

			self.display_command = None
			self.display_data = None
			self.input_event=None
			self.menu_active = True
			self.menu_time = time.time()
			self._menu_display(command)
