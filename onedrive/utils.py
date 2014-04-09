#!/usr/bin/python

import os, sys, pwd, yaml, subprocess, platform
import gtk, webkit

# Prepare global variables

APP_CLIENT_ID = "000000004010C916"
APP_SECRET = "PimIrUibJfsKsMcd0SqwPBwMTV7NDgYi"

HOME_PATH = os.path.expanduser("~")
OS_USER = os.getenv("SUDO_USER")
if OS_USER == None or OS_USER == "":
	# the user isn't running sudo
	OS_USER = os.getenv("USER")
else:
	# when in SUDO, fix the HOME_PATH
	# may not be necessary on most OSes
	HOME_PATH = os.path.split(HOME_PATH)[0] + "/" + OS_USER

OS_DIST =  platform.linux_distribution()

APTITUDE_PKG_DEPENDENCIES = ["dpkg", "git", "python-pip", "libyaml-dev", "python-yaml", "python-dateutil", "inotify-tools", "python-webkit"]
PIP_PKG_DEPENDENCIES = ["urllib3", "requests"]

def queryUser(question, answer = "y"):
	valid = {"y": True, "ye": True, "yes": True,
			 "n": False, "no": False}
	if answer == "y":
		prompt = " [Y/n] "
	elif answer == "n":
		prompt = " [y/N] "
	else:
		prompt = " [y/n] "
	
	sys.stdout.write(question + prompt)
	while True:
		response = raw_input().lower()
		if answer is not None and response == "":
			return answer
		elif response in valid.keys():
			return valid[response]
		else:
			sys.stdout.write("Please respond with 'y' (yes) or 'n' (no).\n")

def mkdirIfMissing(path):
	try:
		if path == "":
			print "The specified path is empty string."
			return False
		if not os.path.exists(path):
			os.mkdir(path, 0700)
			os.chown(path, pwd.getpwnam(OS_USER).pw_uid, pwd.getpwnam(OS_USER).pw_gid)
			print "Created directory \"" + path + "\"."
		return True
	except OSError as e:
		print "OSError({0}): {1}".format(e.errno, e.strerror)
		return False

def checkOSVersion():
	if OS_DIST[0] != "Ubuntu":
		if not queryUser("The package may not support non-Ubuntu based Linux.\nDo you still want to proceed?", "n"):
			print "Stopped."
			sys.exit(0)

def setupDaemon():
	rootPath = ""
	
	print "Setting up OneDrive-d..."
	
	assert mkdirIfMissing(HOME_PATH + "/.onedrive"), "Failed to create the configuration path."
	
	exclusion_list = []
	
	if queryUser("Do you want to exclude some files from being synchronized? ", "y"):
		if queryUser("\t1. Do you want to exclude ViM temporary files?", "y"):
			exclusion_list = exclusion_list + ".*~|\.netrwhist|\.directory|Session\.vim|[._]*.s[a-w][a-z]|[._]s[a-w][a-z]|.*\.un~".split("|")
		if queryUser("\t2. Do you want to exclude emacs temporary files?", "y"):
			exclusion_list = exclusion_list + "\#.*\#|\.emacs\.desktop|\.emacs\.desktop\.lock|.*\.elc|/auto-save-list|\.\#.*|\.org-id-locations|.*_flymake\..*".split("|")
		if queryUser("\t3. Do you want to exclude possibly Mac OS X temporary files?", "y"):
			exclusion_list = exclusion_list + "\.DS_Store|\.AppleDouble|\.LSOverride|\._.*|\.Spotlight-V100|\.Trashes".split("|")
		
		if exclusion_list != []:
			exclusion_list = "exclude: ^(" + "|".join(exclusion_list) + ")$\n"
		else:
			print "There is nothing in the exclusion list."
	else:
		print "Skipped."
	
	while True:
		sys.stdout.write("Please specify the directory to sync with OneDrive (default: " + HOME_PATH + "/OneDrive):\n")
		response = raw_input().strip()
		if mkdirIfMissing(response):
			f = open(HOME_PATH + "/.onedrive/user.conf", "w")
			rootPath = os.path.abspath(response)
			f.write("rootPath: " + rootPath + "\n")
			if exclusion_list != "":
				f.write(exclusion_list)
			f.write("confVer: 0.6\n")
			f.close()
			break
		else:
			sys.stdout.write("Failed to create the directory \"" + response + "\". Please specify another one.\n")
		
	sh = """
#!/bin/sh

### BEGIN INIT INFO
# Provides:          onedrive-d
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start daemon at boot time
# Description:       Enable service provided by daemon.
### END INIT INFO

DAEMON_NAME=onedrive-daemon
DAEMON_PATH=/usr/local/bin/onedrive-daemon

DAEMON_USER="$SUDO_USER"
if [ "${#DAEMON_USER}" -eq "0" ]; then
	DAEMON_USER="$USER"
fi

PIDFILE=/var/run/$DAEMON_NAME.pid

. /lib/lsb/init-functions

do_start () {
	log_daemon_msg "Starting daemon $DAEMON_NAME"
	start-stop-daemon --start --background --pidfile $PIDFILE --make-pidfile --user $DAEMON_USER --startas $DAEMON_PATH
	log_end_msg $?
}

do_stop () {
	log_daemon_msg "Stopping daemon $DAEMON_NAME"
	start-stop-daemon --stop --pidfile $PIDFILE --retry 10 --signal INT
	log_end_msg $?
}

case "$1" in

	start|stop)
		do_${1}
		;;

	restart|reload|force-reload)
		do_stop
		do_start
		;;

	status)
		status_of_proc "$DAEMON_NAME" "$DAEMON_NAME" && exit 0 || exit $?
		;;
	
	*)
		echo "Usage: /etc/init.d/$DAEMON_NAME {start|stop|restart|status}"
		exit 1
		;;
esac

exit 0

"""
	
	print "Installing the daemon script..."
	subp = subprocess.Popen(["cat - > /etc/init.d/onedrive-d && chmod u+x /etc/init.d/onedrive-d"], stdin=subprocess.PIPE, shell=True)
	subp.stdin.write(sh)
	ret = subp.communicate()
	subp.stdin.close()
	assert subp.returncode == 0
	print "Daemon script has been written to /etc/init.d/onedrive-d"
	
	print "Finished setting up the program."
	
def installPackages():
	if queryUser("Do you want to run apt-get update && apt-get upgrade?", "y"):
		subprocess.Popen(["sudo", "apt-get", "update"]).communicate()
		subprocess.Popen(["sudo", "apt-get", "upgrade"]).communicate()
		print "System package list has been updated successfully."
	
	print "Now install pre-requisite system packages..."
	subp = subprocess.Popen(["sudo", "apt-get", "-y", "install"] + APTITUDE_PKG_DEPENDENCIES)
	subp.communicate()
	assert subp.returncode == 0
	
	print "Now install the required PIP packages..."
	for p in PIP_PKG_DEPENDENCIES:
		subprocess.Popen(["sudo", "pip", "install", p, "--upgrade"]).communicate()
	
	print "Now install python-skydrive package..."
	subprocess.Popen(["sudo", "pip", "install", "git+https://github.com/mk-fg/python-skydrive.git#egg=python-skydrive[standalone]", "--upgrade"]).communicate()
	
	print "All the pre-requisite packages have been installed / upgraded."

def liveView_load_finished(webview, frame):
	url = frame.get_uri()
	if "https://login.live.com/oauth20_desktop.srf" in url:
		subp = subprocess.Popen(["skydrive-cli", "auth", url])
		ret = subp.communicate()
		if subp.returncode != 0:
			if queryUser("Authentication failed. Do you want to retry?", "y"):
				# subp.kill()
				gtk.main_quit()
				authDaemon()
			else:
				print "Authentication failed. OneDrive-d will not work."
				sys.exit(0)
		else:
			os.chown(HOME_PATH + "/.lcrc", pwd.getpwnam(OS_USER).pw_uid, pwd.getpwnam(OS_USER).pw_gid)
			print "Authenticated successfully."
			gtk.main_quit()

def w_delete_event(widget, event, data=None):
	print "Authentication window closed."
	widget.destroy()
	gtk.main_quit()
	return False

def authDaemon():
	print "Authenticating..."
	
	# write down app information
	f = open(HOME_PATH + "/.lcrc", "w")
	f.write("client:\n  id: " + APP_CLIENT_ID + "\n  secret: " + APP_SECRET + "\n")
	f.close()
	
	from skydrive import api_v5, conf
	authUrl = api_v5.PersistentSkyDriveAPI.from_conf(None).auth_user_get_url() + "&display=touch"
	
	liveView = webkit.WebView()
	sw = gtk.ScrolledWindow()
	sw.add(liveView)
	liveView.connect("load-finished", liveView_load_finished)
	win = gtk.Window(gtk.WINDOW_TOPLEVEL)
	win.set_default_size(360, 500)
	win.set_position(gtk.WIN_POS_CENTER)
	win.connect('destroy', gtk.main_quit)
	win.connect('delete-event', w_delete_event)
	win.add(sw)
	win.show_all()
	liveView.open(authUrl)
	gtk.main()
		
if __name__ == "__main__":
	if len(sys.argv) < 2:
		print "Usage: sudo onedrive-utils [pkg|setup|auth|all]\n" + " * pkg: install or upgrade pre-requisite packages\n * setup: install and configure onedrive-d\n * auth: authenticate onedrive-d\n * all: do all the steps above"
		sys.exit(1)
	checkOSVersion()
	argv = sys.argv
	if argv[1] == "setup":
		setupDaemon()
	elif argv[1] == "pkg":
		installPackages()
	elif argv[1] == "auth":
		authDaemon()
	elif argv[1] == "all":
		installPackages()
		setupDaemon()
		authDaemon()
		print "All done."
