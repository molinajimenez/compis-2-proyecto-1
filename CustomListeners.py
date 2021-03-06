from DecafListener import DecafListener
from DecafParser import DecafParser
from Intermediator import Intermediator
from SymbolTable import StructTableItem, TableItem, ScopeTableItem

class CustomListener(DecafListener):
    def __init__(self) -> None:

        #sizes management
        self.primitives = ['int', 'char', 'boolean', 'struct', 'void']
        self.defaults = {'int': 0, 'char': 'a', 'boolean': 'false' }
        self.sizes = {'int': 4, 'char': 1, 'boolean': 1}
        self.offset = 0

        #Symbol table
        self.currentMethodName = ''
        self.currentScope = 'global'
        
        self.previousScope = None
        self.scopes = {}
        self.structs = {}
        self.structStack = []
        self.nest = 1
        self.loopCounter = 1
        self.ifCounter = 1
        self.addScope('global')
        #type and return management
        self.nodeTypes = {}
        #error management
        self.errors = []

        #intermedio
        self.writer = Intermediator('.code.txt')
        #mauska herramienta misteriosa! ;)
        self.nodeTempVars = {}
        #contador de Ts 
        self.tempCount = 0

    #ERRORS
    def add_errors(self, errorTitle, entry, line):
        self.errors.append(f"{errorTitle}: {entry}, at line {line}")

    #MEMORY MANAGEMENT
    def getSize(self, num, tipo):
        
        try:
            if tipo in self.primitives:
                return int(num) * self.sizes[tipo]
            else:
                #offset struct.
                return int(num) * self.structs[tipo].size
        except KeyError:
            pass

    def getStructPropertyOffset(self, fullCall, var):            
        properties = fullCall.split('.')
        #no necesitamos sumar el offset del padre.
        properties.pop(0)

        offset = var.offset
        structMembers = self.searchStruct(var.varType).structMembers
        changed = True
        if len(properties) > 0:
            while changed:
                changed = False
                for prop in structMembers:
                    idx = properties[-1].find('[')
                    if idx > -1:
                        rawName = properties[-1][:idx]
                    else:
                        rawName = properties[-1]
                    if rawName == prop:
                        #buscamos numero
                        if properties[-1].find('[') > -1:
                            number = int(self.getNumber(properties[-1], plain=True))
                        else:
                            number = 1
                        size = structMembers[prop].size * number
                        break
                        
                    else:
                        propertyObj = structMembers[prop]
                        if propertyObj.varType.find('struct') > -1:
                            changed = True
                            break
                        size = structMembers[prop].size
                    offset += size
                if changed:
                    propertyObj = structMembers[prop]
                    structMembers = self.structs[propertyObj.varType].structMembers
                else:
                    changed = False

        return offset

    #TABLE MANAGEMENT
    def addScope(self, pastScope, methodType=None):
        canAdd = False
        if self.currentScope not in self.scopes:
            self.scopes[self.currentScope] = ScopeTableItem(parentKey=pastScope, returnType=methodType, symbolTable={})
            canAdd = True
        else:
            canAdd = False

        return canAdd

    def getNumber(self, node, plain=False, ArrVar=None):
        if plain:
            txt = node
        else:
            txt = node.getText()
        init = txt.find('[')
        end = txt.find(']')

        #revisamos que sea un numero
        try:
            if len(txt) > 1:
                if init != -1 and end != -1:
                    a = int(txt[init+1:end])
                    return txt[init+1:end]
                else:
                    return int(txt)
            else:
                a = int(txt)
                return txt
        except:

            #si truena: puede ser una variable, o un metodo.
            #solucion de Bidkar
            if ArrVar:
                inter = None
                self.addTempVar('int', 1, False)
                var, scope = self.findSymbolTableEntry(f't{self.tempCount-1}', self.currentScope)
                #si es exp
                if isinstance(node, DecafParser.LocationExpContext):
                    inter=self.nodeTempVars.get(node.getChild(0).getChild(2))
                elif isinstance(node, DecafParser.LocationContext):
                    inter=self.nodeTempVars.get(node.getChild(2))

                if inter:
                    pass
                else:
                    if len(txt) > 1 and end != -1:
                        inter, scope = self.findSymbolTableEntry(txt[init+1:end], self.currentScope)
                    else:
                        inter, scope = self.findSymbolTableEntry(txt, self.currentScope)
                    
                #si es string, es una temporal 
                if not isinstance(inter, str):
                    inter = self.writer.getVariableCode(inter, self.currentScope, self, num=1)
                #si es primitivo
                if ArrVar.varType in self.primitives:
                    self.writer.writeLine(f'{var.name} = {inter} * {self.sizes[ArrVar.varType]}', self.nest)
                else:
                    self.writer.writeLine(f'{var.name} = {inter} * {int(ArrVar.size / ArrVar.num)}', self.nest)
                
                return var.name

            #esto extrae el valor de la variable.
            loop = False
            if init != -1 and end != -1:
                search = txt[init+1:end]
                var, scope = self.findSymbolTableEntry(search, self.currentScope)
            else:
                search = txt
                var, scope = self.findSymbolTableEntry(search, self.currentScope)

            try:
                a = int(var.value)
            except:
                #asumimos que es una temp o una variable
                loop = True

            while loop:
                var, scope = self.findSymbolTableEntry(var.value, self.currentScope)
                try:
                    a = int(var.value)
                    loop = False
                except:
                    pass
            

            return var.value

        
        

    def pushScope(self, scope):
        self.previousScope = self.currentScope
        self.currentScope = scope


    def isGlobal(self, name):
        isGlobal = False
        table = self.scopes['global'].symbolTable

        if name in table:
            isGlobal = True

        return isGlobal


    def addVar(self, varType, name, decafType, num, isArray, value=None):
        if (num == None): 
            num = 1
        
        canAdd = False
        currentVarSize = self.getSize(num, varType)

        # Gets the SymbolTable from the current scope
        tempSymbolTable = self.scopes[self.currentScope].symbolTable

        if name not in tempSymbolTable:
            tempSymbolTable[name] = TableItem(varType, name, num, decafType, currentVarSize, isArray, self.offset, value=value)
            self.offset += currentVarSize
            canAdd = True
        else:
            canAdd = False

        self.scopes[self.currentScope].symbolTable = tempSymbolTable
        return canAdd

    def addTempVar(self, varType, num, isArray):
        self.addVar(varType, f't{self.tempCount}', 'tempVar', num, isArray, value=self.defaults[varType])
        self.tempCount += 1
        

    #STRUCT MANAGEMENT
    def addStruct(self, structId):
        name = structId
        structId = "struct"+structId
        if structId not in self.structs:
            self.structs[structId] = StructTableItem(structId=structId, structMembers={})
        
    """
    varType: Tipo de variable
    structName: Nombre de estructura a la que se le agrega la variable
    varName: Nombre de la variable
    varContext: tipo de variable
    num: Cantidad de variables que se van a crear > 1 si es un array
    isArray: Bandera que indica si algo es un array
    """
    def addStructProperty(self, varType, structName, varName, varContext, num, isArray):
        if not num: 
            num = 1

        added = False
        currentVarSize = self.getSize(num, varType)

        structId = "struct"+structName
        structProperties = self.structs[structId].structMembers
        tempStructSize = self.structs[structId].size

        if varName not in structProperties:
            structProperties[varName] = TableItem(varType, varName, num, varContext, currentVarSize, isArray, self.offset)
            tempStructSize += currentVarSize
            added = True
        else:
            added = False

        self.structs[structId].structMembers = structProperties
        self.structs[structId].size = tempStructSize
        return added

    def searchStruct(self, name):
        target = None
        if name in self.structs.keys():
            target = self.structs[name]

        return target
    
    def enterVarDeclaration(self, ctx: DecafParser.VarDeclarationContext):
        value = None 
        isArray = False
        varType = ctx.getChild(0).getText()
        varId = ctx.getChild(1).getText()

        if 'struct' in varType:
            found = self.searchStruct(varType)
            if not found: 
                self.nodeTypes[ctx] = '-1'
                self.add_errors('Undeclared struct', 'struct has not been defined', ctx.start.line)
            else:
                
                isArray = ctx.NUM()
                if not isArray:
                    isArray = False
                    num = 1
                else:
                    isArray = True
                    num = self.getNumber(ctx.getChild(3))
                if not isinstance(ctx.parentCtx, DecafParser.StructDeclarationContext):
                    self.addVar(varType, varId, 'structVar', num, isArray)
                        
        else:
            if not isinstance(ctx.parentCtx, DecafParser.StructDeclarationContext):
                
                isArray = ctx.NUM()
                if not isArray:
                    isArray = False
                    num = 1
                else:
                    isArray = True
                    num = self.getNumber(ctx.getChild(3))
                
                added = self.addVar(varType, varId, "var", num, isArray, value=self.defaults[varType])

                if added:
                    self.nodeTypes[ctx] = 'void'
                else:
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors("Scope error", "variable already exists!", ctx.start.line)



    def enterMethodDeclaration(self, ctx: DecafParser.MethodDeclarationContext):
        methodType = ctx.getChild(0).getText()
        methodName = ctx.getChild(1).getText()

        
        self.currentMethodName = methodName
        self.pushScope(methodName)

        #Se crea el scope
        added = self.addScope(self.previousScope, methodType)

        if (added):
            self.nodeTypes[ctx] = methodType
        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors("Method declaration error","Method already exists!",ctx.start.line )

    
        # CODIGO INTERMEDIO
        self.writer.writeLine(f'function {methodName}: ', self.nest-1)

    
    def enterParameter(self, ctx: DecafParser.ParameterContext):
        isArray = False
        if (ctx.getChildCount() > 2): 
            isArray=True

        paramType = ctx.getChild(0).getText()

        if paramType != 'void':
            paramId = ctx.getChild(1).getText()
            if paramType in self.primitives:
                added = self.addVar(paramType, paramId, "param", None, isArray, value=self.defaults[paramType])
            else:
                added = self.addVar(paramType, paramId, "param", None, isArray, value=self.defaults[paramType])
            if (added):
                self.nodeTypes[ctx] = paramType
                target, _ = self.findSymbolTableEntry(paramId, self.currentScope)
                self.writer.writeLine(f'\tPARAMETER vArr[{target.offset}]')
            else:
                self.nodeTypes[ctx] = '-1'
                errorMsg = f"{paramId} parameter already exists!"
                self.addError("ParamError", errorMsg, ctx.start.line)


    def enterStructDeclaration(self, ctx: DecafParser.StructDeclarationContext):
        structId = ctx.getChild(1).getText()
        self.addStruct(structId)

        #populamos el struct 
        for dec in ctx.varDeclaration():
            varType = dec.getChild(0).getText()
            varId = dec.getChild(1).getText()

            isArray = dec.NUM()
            if not isArray:
                isArray = False
                num = 1
            else:
                isArray = True
                #TODO: Mejorar obtener el numero del array...
                num = int(dec.getChild(3).getText())
                
            added = self.addStructProperty(varType, structId, varId, "structVar", num, isArray)
            
            if added:
                self.nodeTypes[ctx] = 'void'
            else:
                self.nodeTypes[ctx] = '-1'
                self.add_errors('Scope error', 'variable already exists!', ctx.start.line)




    def enterLocation(self, ctx: DecafParser.LocationContext):
         if (ctx.location()):
            varId = ctx.getChild(0).getText()
            #si no estamos buscando dentro de un struct..
            if (self.structStack == []):
                structVarType, scope = self.findSymbolTableEntry(varId, self.currentScope)
                structToUse = self.searchStruct(structVarType.varType)
                self.structStack.append(structToUse)
            else:
                #si no buscamos en el ultimo, la variable del struct y si esta en su def
                try:
                    structVarType = self.structStack[-1].structMembers[varId]
                except:
                    self.add_errors('Unexisting property', f'struct missing {varId} property', ctx.start.line)
                structToUse = self.searchStruct(structVarType.varType)
                self.structStack.append(structToUse)

    def enterBlock(self, ctx: DecafParser.BlockContext):
        parentCtx = ctx.parentCtx
        first = parentCtx.getChild(0).getText()

        if first not in self.primitives:
            blockname = self.currentMethodName + str(self.nest)
            #INTERMEDIATE CODE
            #Obtiene el IF_TRUE, IF_FALSE, WHILE_TRUE
            self.writer.getCallers(self,parentCtx, ctx)

            self.nest += 1
            self.pushScope(blockname)

        
        add = self.addScope(self.previousScope)
        if add:
            self.nodeTypes[ctx] = 'void'

        else:
            self.nodeTypes[ctx] = '-1'

        

    
    def exitBlock(self, ctx: DecafParser.BlockContext):
        #Se sale de un scope.
        current = self.methodFinder(self.currentScope)
        self.nest -= 1
        self.writer.writeLine('BLOCK', self.nest)
        self.pushScope(current.parent)
        

    def exitMethodDeclaration(self, ctx: DecafParser.MethodDeclarationContext):
        methodName = ctx.getChild(1).getText()
        if (methodName == 'main'):
            self.mainFound = True

        self.nest = 1
        self.currentMethodName = "global"

        self.pushScope("global")
        self.writer.getTails(self, ctx.parentCtx, ctx)
    
    def exitMethodCall(self, ctx: DecafParser.MethodCallContext):
        name = ctx.getChild(0).getText()


        methodRef = self.methodFinder(name)
        if methodRef:
            calls = []

            for i in range(2, len(ctx.children)-1):
                if(ctx.getChild(i).getText() != ','):
                    calls.append(self.nodeTypes[ctx.getChild(i)])
            
            #Checkeo si esta bien llamada la firma del metodo
            methodSig = self.paramCheck(methodRef, calls)

            if methodSig:
                self.nodeTypes[ctx] = methodRef.returnType

                #INTERMEDIATE

                #CHECK RECURSIVE
                if name == self.currentScope and name.find('WHILE') == -1:
                    self.writer.writeLine(f'RECURSIVE', self.nest)

                #params
                for elem in ctx.expression():
                    param = elem.getText()
                    res1, res2 = self.writer.getOperators(self, elem, None)
                    #encontrar temp
                    if res1.find('t') > -1:
                        x, sc = self.findSymbolTableEntry(res1, self.currentScope)
                        res1 = f'vArr[{x.offset}]'
                    self.writer.writeLine(f'PARAM {res1}', self.nest)
                
                self.writer.writeLine(f'CALL {name}, {len(ctx.expression())}', self.nest)


            else:
                self.nodeTypes[ctx] = '-1'
                self.add_errors('Method call error', 'param missmatch, check method call', ctx.start.line)
                return

        else:
            self.add_errors('Method call error', f'method {name} doesnt exist', ctx.start.line)

        
        
        
    
    def exitMethodCallExp(self, ctx: DecafParser.MethodCallExpContext):
        self.nodeTypes[ctx] = self.nodeTypes[ctx.methodCall()]
        #self.writer.writeLine(f'CALL {name}', self.nest)

    def exitReturnSt(self, ctx: DecafParser.ReturnStContext):
        if ctx.getChild(0).getText() == 'return':
            method = self.getParentMethod(self.currentScope)
            varRet = ctx.getChild(1)

            if ctx.getChild(1).getText() == '':
                if method.returnType == 'void':
                    self.nodeTypes[ctx] = 'void'
                else:
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors('Return type error', f'check method definition', ctx.start.line)
                    return

            else:
                exprType = self.nodeTypes[varRet.getChild(0)]

                if exprType == method.returnType:
                    self.nodeTypes[ctx] = method.returnType

                else:
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors('Return type error', f'check method return type and returning entity', ctx.start.line)
                    return

        #INTERMEDIATE
        op1, op2 = self.writer.getOperators(self, ctx.getChild(1), None)
        if op1.find('t') > -1:
            op1, sc = self.findSymbolTableEntry(op1,self.currentScope)
            op1 = op1.offset
            self.writer.writeLine(f'RETURN vArr[{op1}]', self.nest)
        else:
            self.writer.writeLine(f'RETURN {op1}', self.nest)
    
    
    def exitSumOp(self, ctx: DecafParser.SumOpContext):
        op1 = ctx.getChild(0)
        op2 = ctx.getChild(2)
        operator = ctx.getChild(1).getText()
        if(self.nodeTypes[op1] == 'int' and self.nodeTypes[op2] == 'int'):
            self.nodeTypes[ctx] = 'int'
            #creamos el lado izquierdo del three address code..
            self.addTempVar('int', 1, False)
            #obtenemos la variable recien creada
            targetTemp, scope = self.findSymbolTableEntry(f't{self.tempCount -1}', self.currentScope)

            #agregamos a nodeTemp que deberia saber que ctx apunta a que tempVar
            self.nodeTempVars[ctx] = targetTemp.name
            #self.writer.write(f'{targetTemp.name} = ', self.nest)
            self.writer.write(f'vArr[{targetTemp.offset}] = ')
            x1, x2 = self.writer.getOperators(self, op1, op2)
            self.writer.writeLine(f'{x1} {operator} {x2}')
        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Entity type error', 'arithmetic operator expected integer entities', ctx.start.line)

                
        
        
    
   
    def exitOtherIntOp(self, ctx: DecafParser.OtherIntOpContext):
        op1 = ctx.getChild(0)
        op2 = ctx.getChild(2)
        operation = ctx.getChild(1).getText()
        if(self.nodeTypes[op1] == 'int' and self.nodeTypes[op2] == 'int'):
            self.nodeTypes[ctx] = 'int'

             #creamos el lado izquierdo del three address code..
            self.addTempVar('int', 1, False)
            #obtenemos la variable recien creada
            targetTemp, scope = self.findSymbolTableEntry(f't{self.tempCount -1}', self.currentScope)

            #agregamos a nodeTemp que deberia saber que ctx apunta a que tempVar
            self.nodeTempVars[ctx] = targetTemp.name
            self.writer.write(f'vArr[{targetTemp.offset}] = ', self.nest)
            x1, x2 = self.writer.getOperators(self, op1, op2)
            self.writer.writeLine(f'{x1} {operation} {x2}')

        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Entity type error', 'arithmetic operator expected integer entities', ctx.start.line)

       
    def exitLiteralExp(self, ctx: DecafParser.LiteralExpContext):
        self.nodeTypes[ctx] = self.nodeTypes[ctx.getChild(0)]

    def exitEqOp(self, ctx: DecafParser.EqOpContext):
        op1 = ctx.getChild(0)
        op2 = ctx.getChild(2)
        operation = ctx.getChild(1).getText()
        typeOp = self.nodeTypes[op1]
        typeOp2 = self.nodeTypes[op2]

        if typeOp == typeOp2:
            self.nodeTypes[ctx] = 'boolean'

            #INTERMEDIATE
            #creamos el lado izquierdo del three address code.. 
            if not isinstance(ctx.parentCtx, DecafParser.WhileContext) and not isinstance(ctx.parentCtx, DecafParser.IfContext):
                self.addTempVar('boolean', 1, False)
                #obtenemos la variable recien creada
                targetTemp, scope = self.findSymbolTableEntry(f't{self.tempCount -1}', self.currentScope)

                #agregamos a nodeTemp que deberia saber que ctx apunta a que tempVar
                self.nodeTempVars[ctx] = targetTemp.name
                self.writer.write(f'{targetTemp.name} = ', self.nest)
                x1, x2 = self.writer.getOperators(self, op1, op2)
                self.writer.writeLine(f'{x1} {operation} {x2}')

        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Entity type error', 'comparison operator expected integer entities', ctx.start.line)

        


    def exitRelOp(self, ctx: DecafParser.RelOpContext):
        op1 = ctx.getChild(0)
        op2 = ctx.getChild(2)
        operation = ctx.getChild(1).getText()
        if(self.nodeTypes[op1] == 'int' and self.nodeTypes[op2] == 'int'):
            self.nodeTypes[ctx] = 'boolean'

            #INTERMEDIATE
            #creamos el lado izquierdo del three address code..
            if not isinstance(ctx.parentCtx, DecafParser.WhileContext) and not isinstance(ctx.parentCtx, DecafParser.IfContext):
                self.addTempVar('boolean', 1, False)
                #obtenemos la variable recien creada
                targetTemp, scope = self.findSymbolTableEntry(f't{self.tempCount -1}', self.currentScope)

                #agregamos a nodeTemp que deberia saber que ctx apunta a que tempVar
                self.nodeTempVars[ctx] = targetTemp.name
                self.writer.write(f'{targetTemp.name} = ', self.nest)
                x1, x2 = self.writer.getOperators(self, op1, op2)
                self.writer.writeLine(f'{x1} {operation} {x2}')
        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Entity type error', 'arithmetic operator expected integer entities', ctx.start.line)

       


    def exitCondOp(self, ctx: DecafParser.CondOpContext):
        op1 = ctx.getChild(0)
        op2 = ctx.getChild(2)
        operation = ctx.getChild(1).getText()
        if(self.nodeTypes[op1] == 'boolean' and self.nodeTypes[op2] == 'boolean'):
            self.nodeTypes[ctx] = 'boolean'

            #INTERMEDIATE
            #creamos el lado izquierdo del three address code..
            if not isinstance(ctx.parentCtx, DecafParser.WhileContext) and not isinstance(ctx.parentCtx, DecafParser.IfContext):
                self.addTempVar('boolean', 1, False)
                #obtenemos la variable recien creada
                targetTemp, scope = self.findSymbolTableEntry(f't{self.tempCount -1}', self.currentScope)

                #agregamos a nodeTemp que deberia saber que ctx apunta a que tempVar
                self.nodeTempVars[ctx] = targetTemp.name
                self.writer.write(f'{targetTemp.name} = ', self.nest)
                x1, x2 = self.writer.getOperators(self, op1, op2)
                self.writer.writeLine(f'{x1} {operation} {x2}')

        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Entity type error', 'logical operator expected boolean entities', ctx.start.line)

       

    def exitMinusOp(self, ctx: DecafParser.MinusOpContext):
        op1 = ctx.getChild(1)
        if(self.nodeTypes[op1] == 'int'):
            self.nodeTypes[ctx] = 'int'
        else:
            self.nodeTypes[ctx] = 'error'
            self.add_errors('Entity type error', "minus operator expected an int typed operator", ctx.start.line)
    
    def exitNotOp(self, ctx: DecafParser.NotOpContext):
        op1 = ctx.getChild(0)

        if self.nodeTypes[op1] == 'boolean':
            self.nodeTypes[ctx] = 'boolean'
        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Entity type error', 'logical operator expected boolean entity', ctx.start.line)

    #basic inputs
    def exitParensOp(self, ctx: DecafParser.ParensOpContext):
        self.nodeTypes[ctx] = self.nodeTypes[ctx.expression()] 


    def exitInt_literal(self, ctx: DecafParser.Int_literalContext):
        self.nodeTypes[ctx] = 'int'

    def exitChar_literal(self, ctx: DecafParser.Char_literalContext):
        self.nodeTypes[ctx] = 'char'

    def exitBool_literal(self, ctx: DecafParser.Bool_literalContext):
        self.nodeTypes[ctx] = 'boolean'


    def exitLocationExp(self, ctx: DecafParser.LocationExpContext):
        self.nodeTypes[ctx] = self.nodeTypes[ctx.getChild(0)]

    
    def exitLocation(self, ctx: DecafParser.LocationContext):
        var = None
        if ctx.location() != None:
            if self.structStack != []:
                currentTable = self.structStack.pop()

                if currentTable: 
                    var = currentTable.structMembers[ctx.getChild(0).getText()]

                    if var:
                        self.nodeTypes[ctx] = self.nodeTypes[ctx.location()]
                    else:
                        self.nodeTypes[ctx] = '-1'
                        self.add_errors('Struct definition error', 'non existing property', ctx.start.line)
                else:
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors('Struct definition error', 'property is not a struct', ctx.start.line)
            else:
                var, scope = self.findSymbolTableEntry(ctx.getChild(0).getText(), self.currentScope)
                if var:
                    self.nodeTypes[ctx] = self.nodeTypes[ctx.location()]
                else:
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors('Location error', 'undefined location', ctx.start.line)
        
        elif isinstance(ctx.parentCtx, DecafParser.LocationContext) and not ctx.location():
            if self.structStack != []:
                currentTable = self.structStack.pop()

                if currentTable:
                    var = currentTable.structMembers.get(ctx.getChild(0).getText())
                    if var:  
                        self.nodeTypes[ctx] = var.varType
                    else:
                        self.nodeTypes[ctx] = '-1'
                        self.add_errors('Struct definition error', "Property not found on struct.", ctx.start.line)   
                else:
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors('Struct definition error', "Property not found on struct.", ctx.start.line)   
                       
            else:
                self.nodeTypes[ctx] = '-1'
                self.addError(ctx.start.line, "Parent struct doesn't have this property.")
                
        else:
            var, scope = self.findSymbolTableEntry(ctx.getChild(0).getText(), self.currentScope)
            if var:
                self.nodeTypes[ctx] = var.varType

            else:
                self.nodeTypes[ctx] = '-1'
                self.add_errors('No existing var',f'Var {ctx.getChild(0).getText()} is not defined', ctx.start.line)

            #acceso a array
            if ctx.expression():
                if self.nodeTypes[ctx.expression()] != 'int':
                    self.nodeTypes[ctx] = '-1'
                    self.add_errors('Location error', 'access expression must return an int', ctx.start.line)
                if var:
                    self.nodeTypes[ctx] = var.varType
                    if not var.isArray:
                        self.nodeTypes[ctx] = '-1'
                        self.add_errors('Location error', 'variable is not an array', ctx.start.line)

            else:
                if var:
                    self.nodeTypes[ctx] = var.varType

                    if var.isArray:
                        self.nodeTypes[ctx] = '-1'
                        self.add_errors('Access error', 'index needs to be provided', ctx.start.line)

    def exitVarDeclaration(self, ctx: DecafParser.VarDeclarationContext):
        varType = ctx.getChild(0).getText()
        self.nodeTypes[ctx] = varType

    def exitLiteral(self, ctx: DecafParser.LiteralContext):
        varType = ctx.getChild(0)
        self.nodeTypes[ctx] = self.nodeTypes[varType]

    def exitLiteralExp(self, ctx: DecafParser.LiteralExpContext):
        self.nodeTypes[ctx] = self.nodeTypes[ctx.getChild(0)]

    def exitMethodCallExp(self, ctx: DecafParser.MethodCallExpContext):
        self.nodeTypes[ctx] = self.nodeTypes[ctx.getChild(0)]
        
        self.addTempVar(self.nodeTypes[ctx], 1, False)
        targetTemp, scope = self.findSymbolTableEntry(f't{self.tempCount -1}', self.currentScope)
        self.nodeTempVars[ctx] = targetTemp.name
        call = ctx.getChild(0).getChild(0).getText()
        
        self.writer.writeLine(f'vArr[{targetTemp.offset}] = {call}', self.nest)
        #agregamos a nodeTemp que deberia saber que ctx apunta a que tempVar
        self.nodeTempVars[ctx] = targetTemp.name

        
    def exitAssignSt(self, ctx: DecafParser.AssignStContext):
        op1 = ctx.getChild(0)
        op2 = ctx.getChild(2)

        if self.nodeTypes[op1] == self.nodeTypes[op2]:
            self.nodeTypes[ctx] = self.nodeTypes[op1]

            assign, val = self.writer.getOperators(self, op1, op2)

            if op1.getChildCount() <= 1:
            #hay que buscar la variable y actualizarle el valor.
                varObj, scope = self.findSymbolTableEntry(op1.getText(), self.currentScope)                
                varObj.value = val

            if val.find('t') > -1:
                val, sc = self.findSymbolTableEntry(val, self.currentScope)
                val = f'vArr[{val.offset}]'

            self.writer.writeLine(f'{assign} = {val}', self.nest)

        else:
            self.nodeTypes = '-1'
            self.add_errors('Assignment error', 'variable and value are not the same', ctx.start.line)

        
    
    def enterIf(self, ctx: DecafParser.IfContext):
        expr = ctx.expression()

        op1, op2 = self.writer.getOperators(self, expr.getChild(0), expr.getChild(2))

        if expr.getChildCount() > 1:
            operator = expr.getChild(1).getText()

        #creamos temp
        self.addTempVar('boolean', 1, False)
        storedVal, scope = self.findSymbolTableEntry(f't{self.tempCount - 1}', self.currentScope)
        
        #condicional

        '''
        if expr.getChildCount() > 1:
            self.writer.writeLine(f'{storedVal.name} = {op1} {operator} {op2}', self.nest)
        else:
            self.writer.writeLine(f'{storedVal.name} = {op1}', self.nest)
        '''
        self.writer.writeLine(f'IFZ_{self.ifCounter} {op1} {operator} {op2} GOTO IF_TRUE{self.ifCounter}', self.nest)
        
        self.ifCounter += 1


    def exitIf(self, ctx: DecafParser.IfContext):
        #lo que esta dentro
        expr = ctx.getChild(2)
        
        if self.nodeTypes[expr] == 'boolean':
            self.nodeTypes[ctx] = 'boolean'

            self.writer.writeLine(f'EXIT IF_{self.ifCounter-1}', self.nest)
        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Type error', 'if expression must return boolean', ctx.start.line)

        

    
    def enterWhile(self, ctx: DecafParser.WhileContext):
        expr = ctx.expression()
        
        op1, op2 = self.writer.getOperators(self, expr.getChild(0), expr.getChild(2))
        if expr.getChildCount() > 1:
            operator = expr.getChild(1).getText()
        #creamos temp
        self.addTempVar('boolean', 1, False)
        storedVal, scope = self.findSymbolTableEntry(f't{self.tempCount - 1}', self.currentScope)
        
        #head
        self.writer.writeLine(f'WHILE_{self.loopCounter}:', self.nest)
        

        #condicional
        if expr.getChildCount() > 1:
            self.writer.writeLine(f'{storedVal.name} = {op1} {operator} {op2}', self.nest)
        else:
            self.writer.writeLine(f'{storedVal.name} = {op1}', self.nest)
        
        
        self.writer.writeLine(f'LOOP_COND {op1} {operator} {op2} GOTO END_WHILE_{self.loopCounter}', self.nest)
        self.loopCounter += 1


    def exitWhile(self, ctx: DecafParser.WhileContext):
        #lo que esta dentro
        expr = ctx.getChild(2)
        
        if self.nodeTypes[expr] == 'boolean':
            self.nodeTypes[ctx] = 'boolean'

            #intermediate
            self.writer.getTails(self, ctx.parentCtx, ctx)
        else:
            self.nodeTypes[ctx] = '-1'
            self.add_errors('Type error', 'while expression must return boolean', ctx.start.line)
        
        
    
    def exitProgram(self, ctx: DecafParser.ProgramContext):
        
        if "main" not in self.scopes.keys():
            self.add_errors("Missing method",
                            "missing main() method", ctx.start.line)

        #cerramos el file
        self.writer.f.close()

        

    def findSymbolTableEntry(self, name, scope):
        targetSymbolTable = self.scopes[scope].symbolTable
        search = None

        if name in targetSymbolTable:
            search = targetSymbolTable[name]
        else:

            if scope == 'global' and not search:
                return 
            elif not search and scope != 'global': 
                otherScope = self.scopes.get(scope).parent

            elif scope == 'global' and search:
                return search, scope

            #busca recursivamente hacia arriba
            if otherScope:
                try:
                    search, scope = self.findSymbolTableEntry(name,otherScope)
                    return search, scope

                except:
                    return None, None

        return search, scope

    def methodFinder(self, methodId):
        obj = self.scopes.get(methodId)
        return obj


    def getParentMethod(self, scope):
        targetParent = self.scopes[scope]
        if targetParent.parent != 'global':
            targetParent = self.getParentMethod(targetParent.parent)

        return targetParent
    def updateSymbolTableEntry(self, name, scope):
        pass

    def findMethod(self, name):
        method = self.scopes.get(name)
        return method

    def paramCheckMethod(self, scope, check):
        isCorrect = False
        parent = self.getParentMethod(scope)
        parentSymbolT = parent.symbolTable
        params = []

        for name, varObj in parentSymbolT.items():
            if varObj.decafType == 'param':
                params.append(varObj.name)
        
        if check in params:
            isCorrect = True
        
        return isCorrect

    
    def paramCheck(self, methodObj, callTypes):
        symbol = methodObj.symbolTable
        methodTypes = []
        for varId, varItem in symbol.items():
            if varItem.decafType == "param":
                methodTypes.append(varItem.varType)

        if (callTypes == methodTypes):
            return True 
        else:
            return False