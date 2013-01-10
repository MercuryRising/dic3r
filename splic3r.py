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

	# We loop through the different infill densities, grabbing the fill patterns when necessary
	# and command 
	files = []
	# Index allows us to grab fill patterns or other properties if they're there, density is the infill density we'll use
	for index, density in enumerate(densities):
		if fillPatterns:
			fillPattern = fillPatterns[index]
		print '\nSlicing %s at density %s' %(filePath, density)
		
		# Call slic3r with command line options
		output = subprocess.check_output([slicerPath, '--load', configFile, '--gcode-comments', '--bottom-solid-layers',\
										 '0', '--fill-pattern', fillPattern, '--fill-density', density, '--layer-height',\
										  str(layerHeight), '--first-layer-height', str(firstLayerHeight), filePath])

		# Grab the output filename from slic3r
		fileName = re.findall("Exporting G-code to (.*)", output)[0]

		# Grab the extension from the filename
		fileExtension = fileName.split('.')[-1]

		# Open up the file that slic3r created
		data = grab_file(fileName)

		# Create a new file path, as when we call slic3r again our original file will be gone
		newFilePath = filePath[:-4]+'_graded_'+density[1:]+'.'+fileExtension

		# Make the new file
		with open(newFilePath, 'wb') as f:
			f.write(data)

		# Save it!
		print 'Saved %s successfully' %newFilePath

		# Add the data to the list of files
		files.append(data)

	return files, time.time()-sliceStartTime

def splice_gcode(fillA, fillB, sliceTime=None):

	# Convert the decimal height into the correct axis coordinate
	layerSwitch = "Z"+str(layerSwitchHeight)

	# Convert the data to lines
	fillALines = fillA.split("\n")
	fillBLines = fillB.split("\n")

	# lineB and lineA are the lines where the transition will occur
	# We initialize lineB to 0 to go into 'interactive' mode if the Z-height is not in the file
	lineB = 0
	while not lineB:
		lineB = re.findall(r"(.*?%s.*)" %layerSwitch, fillB)
		if not lineB:
			newSwitch = raw_input("\nYour Z didn't work! Enter a new Z height! > ")
			layerSwitch = "Z"+newSwitch

	# Grab the last occurrence of the Z height to transition at
	lineB = lineB[-1]

	# if the line does not have an A/E position in it, we need to find out what the last extruder position was
	# so we can transition nicely
	index = fillBLines.index(lineB)
	while extruderModifier not in lineB:
		index += 1 
		lineB = fillBLines[index]
		aPositionB = re.findall(r"(%s[-.0-9]*)" %extruderModifier, lineB)[0]

	else:
		aPositionB = re.findall(r"(%s[-.0-9]*)" %extruderModifier, lineB)[0]

	lineA = re.findall(r"(.*?%s.*)" %layerSwitch,fillA)[-1]

	if extruderModifier not in lineA:
		index =fillALines.index(lineA)
		aPositionA = re.findall(r"(%s[-.0-9]*)" %extruderModifier,fillALines[index+1])[0]
	else:
		aPositionA = re.findall(r"(%s[-.0-9]*)" %extruderModifier, lineA)[0]

	print 'First extruder position: ', aPositionA[1:], ' Second extruder position: ', aPositionB[1:]
	diff = float(aPositionB[1:]) - float(aPositionA[1:]) # offset we need for A steps to add to second file
	print 'Density Offset: ', diff

	firstPart = fillB.split(lineB)[0]+lineB.strip()+' (end first part)\n'

	secondPart =fillALines[fillALines.index(lineA)+1:]

	modifiedSecondPart = []
	for index, line in enumerate(secondPart):
		if extruderModifier in line:
			if ";" in line and line.index(";") < line.index("A"): 
				pass
			else:
				aPosition = re.findall(r"(?<!;)(%s[-.0-9]*)" %extruderModifier, line)[0]
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
		print 'Total time: %.1fs Slice time: %.1fs Splice time: %.1fs' %(totalTime, sliceTime, totalTime-sliceTime)
	else:
		print 'Total time: %.1fs' %(totalTime)

def find_extrema(axis, data):
	maximum = 0
	minimum = 9999
	for line in data.split("\n"):
		print repr(line)
		if ";" in line and axis in line and line.index(";") < line.index(axis) or axis not in line:
			pass
		else:

			position = re.findall(r"%s([-.0-9]*)" %axis, line)[0]
			position = float(position)
			if position > maximum:
				maximum = position
			elif position < minimum:
				minimum = position
	return maximum, minimum

def gcode_file_splicer(filePath1, filePath2):
	fillA = grab_file(filePath1)
	fillB = grab_file(filePath2)
	splice_gcode(fillA, fillB)

def tiler(stlFilePath):
	densityData, sliceTime = command_slic3r(stlFilePath)
	fillA, fillB = densityData

	for data in [fillA]:
		for axis in ["X", "Y", "Z", "A"]:
			maximum, minimum = find_extrema(axis, data)
			print "%s max: %f min: %f" %(axis, maximum, minimum) 

	newB = offset(fillB, find_extrema("X", fillA)[0]+10, "X")

	with open("offsetFile.ngc", "wb") as f:
		newBLines = newB.split("\n")
		fillBLines = fillB.split("\n")
		data = zip(fillBLines, newBLines)
		data = [A+" | " + B for A,B in data]
		data = '\n'.join(data)
		f.write(data)

def slice_file(stlFilePath):
	'''
	This function slices an STL into separate densities.
	'''
	densityData, sliceTime = command_slic3r(stlFilePath)
	fillA, fillB = densityData

	splice_gcode(fillA, fillB, sliceTime)

def offset(data, offset, axis):
	newData = []
	for line in data.split("\n"):
		if ";" in line and axis in line and line.index(";") < line.index(axis) or axis not in line:
			pass
		else:
			position = re.findall(r"%s([-.0-9]*)" %axis, line)[0]
			position = float(position)
			newPosition = position + offset
			line = re.sub(axis+str(position), axis+str(newPosition), line)
		newData.append(line)
	return '\n'.join(newData)

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
