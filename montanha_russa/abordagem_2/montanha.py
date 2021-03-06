import os
import sys
import time
from random import randrange
from threading import Thread, Condition, Barrier, Lock
from logging import getLogger, Formatter, FileHandler, StreamHandler, INFO


def setup_logger(logger_name, log_file, level=INFO):
    l = getLogger(logger_name)
    formatter = Formatter('%(message)s')
    fileHandler = FileHandler(log_file, mode='w')
    fileHandler.setFormatter(formatter)
    streamHandler = StreamHandler()
    streamHandler.setFormatter(formatter)

    l.setLevel(level)
    l.addHandler(fileHandler)

setup_logger("info_log", "info.log")
info_log = getLogger("info_log")

setup_logger("carro_log", "carro.log")
carro_log = getLogger("carro_log")

setup_logger("passageiros_log", "passageiros.log")
passageiros_log = getLogger("passageiros_log")


def print_info_log(msg):
    info_log.info(msg)


def print_carro_log(msg):
    print(msg)
    carro_log.info(msg)
    print_info_log(msg)


def print_passageiros_log(msg):
    print(msg)
    passageiros_log.info(msg)
    print_info_log(msg)


"""
Essa abordagem irá fazer o uso de barreiras. É impossível o uso de barreiras para controlar a entrada e saída.
As barreiras são utilizadas para controlar apensas a saída dos passageiros dos veículos, pois um número fixo de
threads é necessário para reativar a barreira. Isso não pode ser feito para a entrada no carro. Considere o caso
em que o caro possui 5 vagas mas há 11 pessoas no parque, das quais 5 estão no veículo, 4 na fila e 2 passeando.
A "barreira" de entrada ficará bloqueada até que 6 threads a desbloqueiem (1 pro carro e 5 para os passageiros).
Entretanto, quando as 2 pessoas que estiverem passeando entrarem na fila, tentarão entrar no veículo que pode não
ter sido unloaded ainda. Por esse motivo, CVs foram usadas para controlar a entrada.
"""

class Carro(object):
    """Carro de uma montanha russa"""

    def __init__(self, limite_pessoas, num_passeios, passageiros=None): #,
        #barreira, lock, condition_variable): #barreira, lock e condition_variables necessitam ser os mesmos enviados
        #aos passageiros
        """Constructor for Car"""
        self.limite_pessoas = limite_pessoas
        self.num_passeios = num_passeios
        if passageiros is None:
            passageiros = []
        self.passageiros = passageiros
        self.fila = []

        self.barr = Barrier(limite_pessoas + 1) #usado para esperar por saida (passageiros + carro)
        self.lk = Lock() #usado para garantir corretude (travar a lista de passageiros)

        #e para cvs (controlar board e unboard)
        self.boardable = False
        self.cv_car = Condition(lock=self.lk) #usado para controle do algoritmo main do carro

        self.thread_main = Thread(target=self.main)
        self.thread_main.start()

    def main(self):
        for x in range(self.num_passeios):
            print_carro_log("Carro: " + str(self) + " passeio nº " + str(x + 1))

            print_carro_log("Carro: " + str(self) + " espera estar cheio para iniciar passeio!")
            self.load()

            print_carro_log("Carro: " + str(self) + " espera terminar o passaio para liberar desembarque!")
            self.run()

            print_carro_log("Carro: " + str(self) + " espera estar vazio para liberar embarque!")
            self.unload()
        os._exit(1)

    def run(self):
        print_carro_log("Carro: " + str(self) + " passeio iniciado!")
        tempo = randrange(5) + 1
        print_carro_log("Carro: " + str(self) + " vai andar por " + str(tempo) + " segundos.")
        time.sleep(tempo)
        print_carro_log("Carro: " + str(self) + " passeio terminado!")

    def load(self):
        print_carro_log("Carro: " + str(self) + " embarque do carro está liberado!")
        self.lk.acquire() #usado para corretude
        while len(self.passageiros) < self.limite_pessoas: #espera carro ficar cheio
            #notifica a primeira pessoa na fila, se houver
            if len(self.fila) > 0:
                print_carro_log("\tLqtd_passageiros: " + str(len(self.passageiros)))
                self.fila[0].cv_fila.notify()
            #volta à dormir. É acordado quando alguém entra no carro ou na fila
            self.cv_car.wait() 
        #self.boardable = False #This is done at unboard to avoid adding more passengers than the max
        self.lk.release() #usado para corretude        

    def unload(self):
        self.lk.acquire() #lock needs to be acquired before cv_wait to assure corretude
        #it is done before barr.wait so the car thread can sleep before any passenger leaves
        self.barr.wait() #releases passengers
        print_carro_log("Carro: " + str(self) + " desembarque do carro está liberado!")
        while len(self.passageiros) > 0: #wait until it is empty. Pode ser acordado quando alguém entrar na fila
            print_carro_log("\tUqtd_passageiros: " + str(len(self.passageiros)))
            self.cv_car.wait()
        self.lk.release() #(once it is notified, it will "reacquire" lock)

    def board(self, passageiro):
        #should have acquired lock previously
        self.fila.pop(0)
        #só chegará nesse ponto quanto for o primeiro da fila e for notificado
        self.passageiros.append(passageiro)
        self.cv_car.notify() #Car is full and will start running
        #mensagem impressa dentro de lock para facilitar compreensao. Idealmente estaria fora
        print_passageiros_log("Passageiro: " + str(passageiro.id_passageiro) + " entrou no carro!" + str(len(self.passageiros)))
        self.lk.release()
        self.barr.wait()

    def unboard(self, passageiro):
        self.lk.acquire()
        self.passageiros.remove(passageiro)
        if len(self.passageiros) == 0:
            self.cv_car.notify()
        #mensagem impressa dentro de lock para facilitar compreensao. Idealmente estaria fora
        print_passageiros_log("Passageiro: " + str(passageiro.id_passageiro) + " saiu do carro!")
        self.lk.release()

    def entrar_fila(self, passageiro):
        passageiro.cv_fila.acquire()
        self.fila.append(passageiro)
        print(" ".join(str(s) for s in self.fila))
        self.cv_car.notify() #notifica que alguém entoru na fila. Carro pode adicioná-lo caso fila
        #estivesse previamente vazia
        passageiro.cv_fila.wait() #espera ser o primeiro da fila



class Passageiro(object):
    """Passageiros de uma montanha russa"""

    id_passageiro = 1

    def __init__(self, carro):
        """Constructor for Passageiro"""
        self.id_passageiro = Passageiro.id_passageiro
        Passageiro.id_passageiro += 1

        self.carro = carro
        self.cv_fila = Condition(self.carro.lk)

        self.thread = Thread(target=self.run)
        self.thread.start()

    def run(self):
        while True:
            self.entrar_fila()
            self.board()
            self.unboard()
            self.passear()

    def entrar_fila(self):
        print_passageiros_log("Passageiro: "+str(self)+" vai Entrar na fila.")
        self.carro.entrar_fila(self)

    def passear(self):
        tempo = randrange(5)+1
        print_passageiros_log("Passageiro: "+str(self)+" vai passear no parque por "+str(tempo)+" segundos enquanto Seu Lobo não vem.")
        time.sleep(tempo)

    def board(self):
        print_passageiros_log("Passageiro: " +str(self)+" vai tentar entrar no carro")
        self.carro.board(self)

    def unboard(self):
        print_passageiros_log("Passageiro: "+str(self)+" vai tentar sair do carro")
        self.carro.unboard(self)

    def __str__(self):
        return str(self.id_passageiro)

# VARIÁVEIS DE CONFIGURAÇÃO
if len(sys.argv) != 4:
    print("Número inválido de argumentos. Exatamente 3 argumentos requeridos, na seguinte ordem:" +
        "\n1 - Número total de passageiros\n2 - Capacidade do carro\n3 - Número máximo de passeios")
    os._exit(1)

num_pessoas = None
limite_pessoas_por_carro = None
passeios_por_carro = None

try:
    num_pessoas = int(sys.argv[1])
    limite_pessoas_por_carro = int(sys.argv[2])
    passeios_por_carro = int(sys.argv[3])
except ValueError:
    print("Argumento(s) inválido(s)! Os 3 argumentos enviados necessitam ser do tipo inteiro")
    os._exit(1)    

if (num_pessoas < limite_pessoas_por_carro):
    print("Erro! Número total de pessoas/passageiros é menor que a capacidade do carro")
    os._exit(1)


carro = Carro(limite_pessoas_por_carro, passeios_por_carro)

passageiros = []
for x in range(num_pessoas):
    passageiros.append(Passageiro(carro))