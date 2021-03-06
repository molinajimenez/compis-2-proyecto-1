
class AssGenerator():
    def __init__(self):
        self.head = ''
        self.main = ''
        self.body = ''
        self.aux = ''
        self.tail = ''
        self.printer = ''
        self.falseStatements = []
        self.f = open('miprog.s', 'w')
        self.registers_av = {"R1": "PARAM","R2": "PARAM", "R3": "PARAM", "R4": "", "R5": "", "R6": "", "R7": "", "R8": "" , "R9": "" , "R10": "", "R11": "", "R12": ""}
        self.asociated_params = {}
        self.translatedParams = {}
        self.memDescriptor = {}
        self.cmpOps = {"<": 'bgt',  "==": "bne", ">": "blt", '>=': 'bgt', '<=': 'blt', '!=': 'bne'}
        self.cmpIfOps = {"<": 'blt', '==': 'beq', '>': 'bgt', '!=': 'bne', '>=': 'bgt', '<=': 'blt'}
        self.flagBranch = None
        self.ifFlag = None
        self.funciones = []
        self.loops = []
        self.gotoSkip = []
        self.intermediate = open('.code.txt', 'r').readlines()
        self.createHead()
        self.createExit()
        self.createTail()
        self.search_alt(self.intermediate)
        self.function_identifier(self.intermediate)
        self.write()


    def createHead(self):
        self.head += """
.global main
.func main\n
"""

    def createTail(self):
        self.tail += ".data \n"
        self.tail += "add_str: \n"
        self.tail += r'.ascii "Adding numbers... \n"'
        self.tail += "\nresult_str: \n"
        self.tail += r'.asciz "Sum = %d\n"'
        self.tail += "\n exit_str: \n"
        self.tail += '.ascii "Terminating program."  '


    # Obtenido de https://raw.githubusercontent.com/cmcmurrough/cse2312/
    def createExit(self):

        #Procedimiento de exit
        self.exit = """
exit:
	MOV R7, #4          @ write syscall, 4
	MOV R0, #1          @ output stream to monitor, 1
	MOV R2, #21         @ print string length
	LDR R1,=exit_str    @ string at label exit_str:
	SWI 0               @ execute syscall


    MOV R7, #1          @ terminate syscall, 1
	SWI 0               @ execute syscall\n"""

    def createPrint(self):
        #procedimiento
        self.printer += """OutputInt:
    PUSH {LR}          @ store LR since printf call overwrites 
    LDR R0,=result_str  @ string at label hello_str: 
    BL printf           @ call printf, where R1 is the print argument 
    POP {PC}\n
"""

    def search_alt(self, content):
        for elem in content:
            if elem.strip().find('IF_FALSE') > -1:
                name = elem.strip().replace(':', '')
                self.falseStatements.append(name)

    def getPriorityReg(self, variable):
        if variable in self.translatedParams.keys():
            return self.translatedParams[variable]
        else:
            return self.getReg(variable)
                
    def function_identifier(self, content):
        paramCounter = 1
        paramPush = 0
        global var
        isRecursive = False
        var = ''
        for number, line in enumerate(content):
            line = line.strip()
            if line.find('function') > -1:
                name = line.split('function')[1].strip()
                functionName = name
                isRecursive = False
                self.funciones.append(name.replace(':',''))
                
                if name.find('OutputInt') <= -1:
                    var += f'{name}\n'

                if name.find('OutputInt') > -1 :
                    self.createPrint()

                if name.find('OutputInt') == -1 and name.find('IF') == -1 and name.find('WHILE') == -1 and name.find('main') == -1:
                    var += '\tPUSH {LR}\n'

            elif line.find(':') > -1 and line.find('OutputInt') <= -1 and line.find('END') <= -1: 
                #es un if condicion
                self.body += var
                var = ''
                var = self.aux
                self.aux = ''
                name = line.strip()
                var += f'{name}\n'

            #convertir instrucciones
            splitted = line.strip().split(' ')
            for i, elem in enumerate(splitted):
                elem = elem.strip()
                
                if '=' in splitted and len(splitted) > 3:
                    if elem == '+':
                        r1 = self.getPriorityReg(splitted[0])
                        r2 = self.getPriorityReg(splitted[i-1])
                        r3 = self.getPriorityReg(splitted[i+1].strip())
                        var  += f" \tADD {r1}, {r2}, {r3} \n"
                        continue
                    elif elem == '-':
                        r1 = self.getPriorityReg(splitted[0])
                        r2 = self.getPriorityReg(splitted[i-1])
                        r3 = self.getPriorityReg(splitted[i+1].strip())
                        var  += f"\tSUB {r1}, {r2}, {r3} \n"
                        continue
                    elif elem == '*':
                        r1 = self.getPriorityReg(splitted[0])
                        r2 = self.getPriorityReg(splitted[i-1])
                        r3 = self.getPriorityReg(splitted[i+1].strip())
                        var  += f"\tMUL {r1},  {r2}, {r3} \n"
                        continue

                elif elem == '=' and not len(splitted) > 3:
                    
                    if splitted[-1] in self.funciones:
                        var  += f"\tMOV {self.getReg(splitted[i-1])}, R0\n"
                    else:
                        var  += f"\tMOV {self.getReg(splitted[i-1])}, {self.getReg(splitted[-1].strip())}\n"

                    if splitted[-1].find('t') > -1:
                        self.freeReg(splitted[-1].strip())

                    continue

                if elem == 'RETURN':
                    variableToReturn = splitted[i + 1]
                    var  += f'\tMOV R0, {self.getReg(variableToReturn)} \n'
                    if splitted[-1].find('t') > -1:
                        self.freeReg(splitted[-1].strip())
                    var  += '\tPOP {PC} \n \n '

                if elem == 'PARAM':
                    if content[number + 1].find('OutputInt') > -1:
                        var += self.getRegParam(splitted[i+1], 1)
                    else:
                        #revisamos asociados
                        counter = number
                        while line.find('CALL') == -1:
                            counter +=1
                            line = content[counter]

                        toCall = content[counter].split(' ')[1]
                        arrParams = self.asociated_params.get(toCall.replace(',',''))
                        if paramPush > len(arrParams) - 1:
                            paramPush = 0 
                        numberReg = arrParams[paramPush]
                        paramPush +=1
                        var += self.getRegParam(splitted[i+1],numberReg)
                        reg = self.getReg(splitted[i+1])
                       
                        self.registers_av[reg] = splitted[i+1]
                        

                if elem == 'CALL':
                    functionName = splitted[i+1].replace(',','')

                    if functionName.find('OutputInt') > -1:

                        var  += '\tBL OutputInt\n'

                    else:
                        var  += f'\tBL {functionName}\n'
                        if isRecursive:
                            funct = functionName.replace(':','')
                            arr = self.asociated_params[funct]
                            for a in arr:
                                var += '\tPOP {R%s} \n' % a



                if elem.find("END_WHILE") > -1:
                    if elem[-1] == ':' and elem not in self.loops:
                        var  += f'{elem}\n'
                        var += '\tb exit \n'
                        self.loops.append(elem)
                        continue

                if elem.find('RECURSIVE') > -1:
                    isRecursive = True
                    funct = functionName.replace(':','')
                    arr = self.asociated_params[funct]
                    for a in arr:
                        var += '\tPUSH {R%s} \n' % a

                    
                if elem.find("PARAMETER") > -1 and name != 'OutputInt:':
                    register = f'R{paramCounter}'
                    funct = name.replace(':','')
                    #hacemos asociacion
                    try:
                        array = self.asociated_params[funct] 
                    except KeyError:
                        self.asociated_params[funct]  = []

                    array = self.asociated_params[funct]
                    array.append(paramCounter)


                    self.registers_av[register] = 'PARAM'

                    regi = self.getReg(splitted[i+1].strip())

                    var  += f'\tMOV {regi}, {register}\n'

                    self.translatedParams[splitted[i+1]] = register
                    paramCounter += 1

                if elem.find("BLOCK") > -1:
                    #guardamos todo a aux
                    if name.find('WHILE') > -1:
                        name = name.replace(':','')
                        var += f'\tb {name}\n'
                    self.aux += var
                    var = ''
                    #switch..
                    var = self.body
                    self.body = ''

                if elem.find('vArr') > -1:
                    #descriptor..
                    try:
                        self.memDescriptor[elem]
                    except:
                        self.memDescriptor[elem] = int(elem[5:-1]) + 4
                    #var += f'\t@ STR fp,  [sp, #{self.memDescriptor[elem]}]\n'

                #Para operaciones condicionales.
                if elem in self.cmpOps.keys():
                    if splitted[-1].find('IF_') > -1:
                        self.flagBranch = self.cmpIfOps[elem]
                    else:
                        self.flagBranch = self.cmpOps[elem]
                    reg = self.getReg(splitted[i-1])
                    reg2 = self.getReg(splitted[i+1])
                    
                    if splitted[0].find('IFZ') > -1 or splitted[0].find('LOOP_COND') > -1:
                        var  += f'\tcmp {reg}, {reg2}\n'
                        if self.flagBranch != None:    
                            var  += f'\t{self.flagBranch} {splitted[-1].strip()}\n'
                            self.flagBranch = None
                        
                
                if line.find('GOTO') > -1:
                    
                    if splitted[0].strip() == 'GOTO':
                        if splitted[1] not in self.gotoSkip:
                            var  += f'\tb {splitted[1]}\n'
                            self.gotoSkip.append(splitted[1])

                if line.find('EXIT IF') > -1:
                    for falseSt in self.falseStatements:
                        if falseSt[-1] == line[-1]:
                            var += f'\tB {falseSt}\n'
                            self.falseStatements.pop()
                            break

                
                #NO DEBERIAN DE EXISTIR TEMPORALES
                for elem in self.registers_av.keys():
                    val = self.registers_av[elem]
                    if val.find('t') > -1:
                        self.registers_av[elem] = ''

                


    def write(self):
        #headers
        self.f.write(self.head)
        print(self.head)
        #main
        self.f.write(self.main)
        print(self.main)
        #body
        #self.f.write(self.body)
        #print(self.body)
        print('***********')
        #print
        print(self.printer)
        self.f.write(self.printer)
        
        
        #ifs
        self.f.write(self.aux)
        print(self.aux)
        
        self.f.write(self.exit)

        self.f.write(self.tail)

        print('============')
        print(self.registers_av)

        self.f.close()


    def getReg(self, var):
        register = None
        
        
        var = var.strip()
        #Caso: Que ya exista en otro registro la variable buscada, solo llamamos el registro.
        if var.find("[") > -1 or var.find("t") > -1 or var.find('vArr') > -1:
            for i in self.registers_av.keys():
                if self.registers_av[i] == var:
                    register = i
                    break

            if register != None:
                return register
            else:
                #Caso: Si no esta guardado, buscar uno vacio y asignar ese registro
                for i in self.registers_av.keys():
                    if self.registers_av[i] == "" or self.registers_av[i] == '':
                        self.registers_av[i] = var
                        register = i
                        break

                if register != None:
                    return register
                else:
                    #Si no, out of registers...
                    return "-1"
        else:
            #si entra un numero, convertirlo a una etiqueta en assembly
            return "#"+var



    def getRegParam(self, var, counter):
        register = None
        #nuevamente, si es caso que ya existe, ingresar.
        for i in self.registers_av.keys():
            if self.registers_av[i] == var:
                register = i
                break

        #Indicar a que registro
        new_reg = "R" + str(counter)
        content = self.registers_av[new_reg]
        #si encontramos un registro que no sea otro parametro, buscamos
        if "PARAM" not in content and content != "" and register != new_reg and register != None:
            regi3 = None
            for i in self.registers_av.keys():
                #busqueda de uno vacio
                if self.registers_av[i] == "":
                    self.registers_av[i] = var
                    regi3 = i
                    break
            
            #Si encontramos en uno que tenia algo, buscamos sustituir valores, puesto que necesitamos al parametro AHI
            arm_code = "\tMOV " + regi3 + "," + register + "\n"
            arm_code  += "\tMOV " + register + "," + new_reg + "\n"
            arm_code  += "\tMOV " + new_reg + "," + regi3 + "\n"
            
            #Actualizamos tabla de registros
            self.registers_av[register] = content
            self.registers_av[new_reg] = self.registers_av[regi3]
            self.registers_av[regi3] = ""

            return arm_code
        # Si el registro es distinto del nuevo, y no es nulo
        elif register != new_reg and register != None:
            content = content.split(" ")
            #Movemos lo que tenemos a este nuevo registro.
            arm_code = "\tMOV " + new_reg + "," + register + "\n"
            
            return arm_code
        
        elif var == "R0":
            #Si es R0, lo metemos a un registro nuevo
            arm_code = "\tMOV " + new_reg + ", " + var + "\n"
            return arm_code
        else:
            #Guardado de valor.
            arm_code = "\tMOV " + new_reg + ", #" + var + "\n"
            return arm_code
    
    #limpiamos una variable que ya no sirve, esto la habilita segun tabla de registros.
    def freeReg(self, var):
        for i in self.registers_av.keys():
            if self.registers_av[i] == var:
                self.registers_av[i] = ""
                break