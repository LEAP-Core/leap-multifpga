
# parse dangling has been subsumed by other functions in the LI
# library. However, there is still some useful code here related to
# type compression.  We need to scrape this code and resurrect type
# compression.

  def parseDangling(self, platformName):
      # we may have several logfiles. Let's combine them together. 
      lines = []
      for infile in self.platformData[platformName]['LOG']:
          logfile = open(infile,'r')
          print "Examining file " + infile
          for line in logfile:
              lines.append(line)
          logfile.close()
      
    
      parser = TypeParser()

      compressInstanceTypes = {}
      #we will build up a list of compressors by examining all bo
      if(self.ENABLE_TYPE_COMPRESSION):
          for module in self.moduleList.moduleList: 
              print "Examining " + module.name
              command = 'bluetcl ./hw/model/dumpStructures.tcl ' + module.name + ' Compress -p ' + self.platformData[platformName]['BLUETCL']
              print command + "\n"
                          

              tclIn = os.popen(command)
              typeclassRaw = tclIn.read()
              compressable = False
              print "TypeclassRaw:   " + typeclassRaw + "\n"
              typeclass = "None"
              try:
                  typeclass = parser.parseType(typeclassRaw) 
                  for instance in typeclass.instances:
                      if(not (str(instance) in compressInstanceTypes)):
                          print "Adding instance: " + str(instance)

                          compressInstanceTypes[str(instance)] = instance
                                  
              except TypeError:
                  #We need something here even though we don't handle the exception
                  print "No compress typeclass found for " + str(module.name)



      for line in lines:
          # also pull out link widths
          if(re.match('.*SizeOfVia:.*',line)):
            print "XXX: " + line + "\n"
            match = re.search(r'.*SizeOfVia:([^:]+):(\d+)',line)
            if(match):
              print "XXX: " + match.group(1) + "\n"
              self.platformData[platformName]['WIDTHS'][match.group(1)] = int(match.group(2))
              
          if(re.match("Compilation message: .*: Dangling",line)):
              match = re.search(r'.*Dangling (\w+) {(.*)} \[(\d+)\]:(\w+):(\w+):(\w+):(\d+):(\w+):(\w+)', line)
              if(match):
            #python groups begin at index 1  
                  print 'found connection: ' + line
                  if(match.group(1) == "Chain"):
                    print "Got chain " + match.group(3)
                    sc_type = "ChainSrc"
                  else:
                    sc_type = match.group(1)

                  type = LinkType("None",False,[])
                  if(self.ENABLE_TYPE_COMPRESSION):
                      # construct a tagged union structure for this type!                  
                      baseType =  parser.parseType(match.group(2))
                      typeRefs = flatten(baseType.getTypeRefs())


                      def resolveType(typeRef):
                          type = typeRef.name
                          print "Adding ref: " + str(type)
                          # Anonymous structs may have dollar signs in them.  
                          type.replace('$','\$')

                          command = 'bluetcl ./hw/model/dumpStructures.tcl ' + typeRef.namespace + ' ' + type  +  ' -p ' + self.platformData[platformName]['BLUETCL']
                          print command + "\n"
                      
                          tclIn = os.popen(command)
                          raw = tclIn.read()
                          print "Parsing: " + raw
                          refType = parser.parseType(raw)
                          #check in the type ref's bo or in the link's bo or in the top level bo for a 
                          #compressable definition
                          
                          #Did we actually get a non-reference type?
                          if(isinstance(refType, TypeRef)):
                              print "Resolve type recurses\n"  
                              return resolveType(refType)
                          return refType

                      def getDependencies(type):
                          print "Deps: " + str(type.getTypeRefs())
                          print "Deps: " + str(flatten(type.getTypeRefs()))
                          return map(lambda ref: ref.namespace, flatten(type.getTypeRefs())) 

                      # this function looks in a bo file for a
                      # definition of the compressable type class.  If
                      # it finds such a definition 
                      def checkCompressable(type):
                          print "checkCompressable " + str(type)
                          compressable = False
                          instanceDeps = []
                          # Let's look for the Compress typeclass
                          for instance in compressInstanceTypes.values():
                              print "instance: " + str(instance)
                              instanceType = instance.params[0]
                              
                              if(isinstance(instance.params[0],TypeRef)):
                                  #need to dereference types
                                 
                                  if(str(instance.params[0]) in self.platformData[platformName]['TYPES']):
                                      instanceType = self.platformData[platformName]['TYPES'][str(instance.params[0])].type
                                      instanceDeps = self.platformData[platformName]['TYPES'][str(instance.params[0])].dependencies 
                                  else:
                                      instanceType = resolveType(instance.params[0])
                                      # We found a new type.  Memoize it!
                                      print "New instanceType " + str(instanceType)
                                      print "Deps: " + str(getDependencies(instanceType)) 
                                      instanceDeps =  getDependencies(instanceType) + [instance.params[0].namespace]
                                      self.platformData[platformName]['TYPES'][str(instanceType)] = LinkType(instanceType, True, instanceDeps)
                              print "\n\nStarting comparison:  " + str(instanceType)
                              ## == for types is a unification
                              if(instanceType == type):
                                  compressable = True
                                  print "Found a compressable type  " + str(instanceType)
                                  break
                              print "Type comparison failed"
                          if(not compressable):
                              print "Uncompressable type: " + str(type)     
      
                          return [compressable,instanceDeps] 
                      #end checkCompressable

                      
                      #Let's resolve all the type references for fun and profit
                      for ref in typeRefs:
                          print "Handling ref: " + str(ref)
                          if(str(ref) in self.platformData[platformName]['TYPES']):
                              continue
                         
                          print "Adding: " + str(ref)

                          refType = resolveType(ref)
                          [compressable, compressionDeps] = checkCompressable(refType)
                          deps = getDependencies(baseType) + getDependencies(ref)
                          if(compressable):
                              deps += compressionDeps
                          self.platformData[platformName]['TYPES'][str(ref)] = LinkType(refType,compressable,deps)
                         
                          print "parse: " + str(self.platformData[platformName]['TYPES'][str(ref)])
  
                      #Was the original type a reference? If it was, then our loop recovered its type.
                      if(isinstance(baseType,TypeRef)):
                          type = self.platformData[platformName]['TYPES'][str(baseType)] 
                      
                      #If we got no type refs, then this is a base
                      #class. We already parsed it but we may need to
                      #do some level of type binding
                      if(len(list(typeRefs)) == 0):
                          print "Handling baseType: " + str(baseType)

                          if(str(baseType) in self.platformData[platformName]['TYPES']):
                              type = self.platformData[platformName]['TYPES'][str(baseType)] 
                          else:
                              [compressable, compressionDeps] = checkCompressable(baseType)
                              deps = getDependencies(baseType)
                              if(compressable):
                                  deps += compressionDeps
                              type = LinkType(baseType, compressable, deps)
                              self.platformData[platformName]['TYPES'][str(baseType)] = type



                  parentConnection = DanglingConnection(sc_type, 
                                                        match.group(2),
                                                        match.group(3),
                                                        match.group(4),      
                                                        match.group(5),
                                                        match.group(6),
                                                        match.group(7),
                                                        match.group(8),
                                                        match.group(9),
                                                        type)
                           
                  # can we automatically compress?
                  if(isinstance(type.type,TaggedUnion) and self.ENABLE_TYPE_COMPRESSION and (sc_type == 'Recv' or sc_type == 'Send')):
                      compressor = []
                      if(sc_type == 'Recv'):
                          compressor = TaggedUnionCompressor(parentConnection)
                      else:
                          compressor = TaggedUnionDecompressor(parentConnection)
                      
                      # The compressor generates a bunch of
                      # connections.  Add them now. The parent
                      # connection is effectively dead at this point,
                      # as it will be subsumed in the compression code
                      self.platformData[platformName]['DANGLING'] += compressor.channels

                  else: # can't do anything with this link
                      self.platformData[platformName]['DANGLING'] += [parentConnection]

                  if(match.group(1) == "Chain"):
                    self.platformData[platformName]['DANGLING'] += [DanglingConnection("ChainSink", 
                                                                                match.group(2),
                                                                                match.group(3),
                                                                                match.group(4),
                                                                                match.group(5),
                                                                                match.group(6),
                                                                                match.group(7),
                                                                                match.group(8),
                                                                                match.group(9),
                                                                                type)]

              else:
                  print "Error: Malformed connection message: " + line
                  sys.exit(-1)

