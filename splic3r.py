import re
import subprocess
import sys
import time

################## USER PARAMETERS #####################

# where is your slic3r config file? If you don't know, export it now under the file menu of slic3r
configFile = ""

# path to slic3r
slicerPath = ""

# what densities would you like to grade at?
# first one is the first grade to be printed, second will kick in at the set z
densities = ['.2', '.2']

# Fill patterns - must be 1:1 with density, or a blank array []
fillPatterns = ["concentric", "honeycomb"]

# what is the Z-height you would like to splice the stls at?
# you have to pick an actual Z height (no approximations)
# you can pick one from calculating your first layer height + layer heights
layerHeight = .30
firstLayerHeight = .30
layers = 12
layerSwitchHeight = layers*layerHeight

# if using reprap, 'E', if using linuxCNC, 'A'
extruderModifier = "A"

# preferred extension for spliced file
extension = '.ngc'

#########################################################

def grab_file(filePath):
	with open(filePath, 'rb') as f:
		return f.read()

def command_slic3r(filePath):
	'''
	This function makes slic3r slice at the specified infill densities
	Returns two strings containing the gcode for the infills selected
	'''
	sliceStartTime = time.time()
	files = []
	for index, density in enumerate(densities):
		if fillPatterns:
			fillPattern = fillPatterns[index]
		print '\nSlicing %s at density %s' %(filePath, density)
		output = subprocess.check_output([slicerPath, '--load', configFile, '--bottom-solid-layers', '0', '--fill-pattern', fillPattern, '--fill-density', density, '--layer-height', str(layerHeight), '--first-layer-height', str(firstLayerHeight), filePath])
		fileName = re.findall("Exporting G-code to (.*)", output)[0]
		fileExtension = fileName.split('.')[-1]
		data = grab_file(fileName)
		newFilePath = filePath[:-4]+'_graded_'+density[1:]+'.'+fileExtension
		with open(newFilePath, 'wb') as f:
			f.write(data)

		print 'Saved %s successfully' %newFilePath
		files.append(data)

	return files, time.time()-sliceStartTime

def splice_gcode(fill20, fill90, sliceTime=None):
	layerSwitch = "Z"+str(layerSwitchHeight)
	fill20Lines = fill20.split("\n")
	fill90Lines = fill90.split("\n")

	line90 = 0
	while not line90:
		line90 = re.findall(r"(.*?%s.*)" %layerSwitch, fill90)
		if not line90:
			newSwitch = raw_input("\nYour Z didn't work! Enter a new Z height! > ")
			layerSwitch = "Z"+newSwitch
	line90 = line90[-1]

	if extruderModifier not in line90:
		index = fill90Lines.index(line90)
		a90 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, fill90Lines[index+1])[0]
	else:
		a90 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, line90)[0]

	line20 = re.findall(r"(.*?%s.*)" %layerSwitch, fill20)[-1]

	if extruderModifier not in line20:
		index = fill20Lines.index(line20)
		a20 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, fill20Lines[index+1])[0]
	else:
		a20 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, line20)[0]

	print 'A20 step: ', a20[1:], ' A90step: ', a90[1:]
	diff = float(a90[1:]) - float(a20[1:]) # offset we need for A steps to add to second file
	print '\nOffset for densities: ', diff

	firstPart = fill90.split(line90)[0]+line90.strip()+' (end first part)\n'

	secondPart = fill20Lines[fill20Lines.index(line20)+1:]

	modifiedSecondPart = []
	for index, line in enumerate(secondPart):
		if extruderModifier in line:
			#print line
			aPosition = re.findall(r"(%s.*)" %extruderModifier, line)[0]
			newA = float(aPosition[1:])+diff
			line = re.sub(aPosition, extruderModifier+str(newA)+" (%s)"%aPosition, line)

		modifiedSecondPart.append(line)

	data = firstPart + '\n'.join(modifiedSecondPart)

	nfp = stlFilePath[:-4]+"_graded"+extension
	with open(nfp, "wb") as f:
		f.write(data)

	print "\nWrote %s successfully" %nfp
	print "You may want to open the file and search for '(end first part)' to ensure everything is sane."
	totalTime = time.time()-startTime
	if sliceTime is not None:
		print 'Total time: %.1fs Slice time: %.1fs Grade time: %.1fs' %(totalTime, sliceTime, totalTime-sliceTime)
	else:
		print 'Total time: %.1fs' %(totalTime)

def gcode_file_splicer(filePath1, filePath2):
	fill20 = grab_file(filePath1)
	fill90 = grab_file(filePath2)
	splice_gcode(fill20, fill90)

def slice_file(stlFilePath):
	densityData, sliceTime = command_slic3r(stlFilePath)
	fill20, fill90 = densityData
	splice_gcode(fill20, fill90, sliceTime)

if __name__ == '__main__':
	startTime = time.time()

	if not (configFile and slicerPath):
		print "Please open the script and enter the path for slic3r and the slic3r config file"
		sys.exit()
	if len(sys.argv) > 1:
		if len(sys.argv) > 2:
			firstFile = sys.argv[1]
			secondFile = sys.argv[2]
			print 'Using %s and %s as input files...' %(firstFile, secondFile)
			stlFilePath = firstFile
			gcode_file_splicer(firstFile, secondFile)
		else:
			stlFilePath = sys.argv[1]
			print 'Using %s as input file...' %stlFilePath
			slice_file(stlFilePath)
	else:
		print "Please enter an stl file or gcode(s) to grade"
