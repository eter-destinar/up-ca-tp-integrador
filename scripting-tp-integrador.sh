#!/bin/bash
clear

PS3="Seleccione una opcion (Presione ENTER, sin opcion, para ver el menu: "
opciones="Fibonacci Numero_Invertido Palindromos Lineas_archivo Ordenar_Numeros Cantidad_archivos_tipo Salir"

USUARIO=$(whoami)

function opcion_1
{
declare -i NUM1=0
declare -i NUM2=0
declare -i N_FIBO

echo ""
echo "1. Se mostraran la cantidad de elementos de la sucesion de Fibonacci"
echo ""

echo -n "Ingrese la cantidad de elementos a mostrar de la sucesion de Fibonacci: "
read CANTIDAD_FIBO
for  (( i=1; i<=$CANTIDAD_FIBO; i++ ))
do
	if [ $i -eq 1 ]
	then
		NUM1=0
		echo 0
	elif [ $i -eq 2 ]
	then
		NUM2=1
		echo 1
	else
		N_FIBO=$NUM1+$NUM2
		echo $N_FIBO
		NUM1=$NUM2
		NUM2=N_FIBO
	fi
done
}

function opcion_2
{
CADENA1=""
LONGITUD_CADENA=0
CADENA_INVERSA=""

echo ""
echo "2. Se mostrara el numero ingresado en forma inversa"
echo ""

echo -n "Ingrese un numero entero: "
read CADENA1

LONGITUD_CADENA=${#CADENA1}

if [ $LONGITUD_CADENA -eq 1 ]
then
	CADENA_INVERSA=$(( $CADENA1 * 10 ))
	echo $CADENA_INVERSA
else
	for (( i=$LONGITUD_CADENA-1; i>=0; i-- ))
	do
		CADENA_INVERSA="$CADENA_INVERSA${CADENA1:$i:1}"
	done
	echo $CADENA_INVERSA
fi
}

function opcion_3() 
{
CADENA1=""
LONGITUD_CADENA=0
CADENA_INVERSA=""

echo ""
echo "3. Se mostrara si la palabra o frase ingresada es palindromo o no lo es"
echo ""

echo -n "Ingrese una palabra o frase: "
read CADENA1

LONGITUD_CADENA=${#CADENA1}
CADENA1=$(echo "$CADENA1" | tr -d '[[:space:]]')
CADENA1=${CADENA1^^}

for (( i=$LONGITUD_CADENA-1; i>=0; i-- ))
do
	CADENA_INVERSA="$CADENA_INVERSA${CADENA1:$i:1}"
done

if [ $CADENA1 = $CADENA_INVERSA ]
then
	echo "ES PALINDROMO"
else
	echo "NO ES PALINDROMO"
fi
}

function opcion_4
{

echo ""
echo "4. Se mostrara la cantidad de lineas que contiene el archivo indicado"
echo ""

echo -n "Ingresar el PATH de un archivo: "
read ARCHIVO

if [ -f $ARCHIVO ]
then
	echo "EL NUMERO DE LINEAS DEL ARCHIVO ES: $(wc -l < $ARCHIVO)"
else
	echo "EL ARCHIVO NO EXISTE"
fi
}

function opcion_5
{
declare -a A_NUMEROS=()

echo ""
echo "5. Se ingresaran 5 numeros enteros y se mostraran ordenados"
echo ""

for (( i=1; i<=5; i++ ))
do
	echo -n "Ingrese un numero: "
	read NUMERO
	A_NUMEROS[$i]=$NUMERO
done

RESULTADO=$(for (( j=1; j<=5; j++ ));do echo ${A_NUMEROS[$j]};done | sort -n)
echo ""
echo -n "La secuencia ordenada de menor a mayor es: "
echo  ${RESULTADO[*]}
echo ""
}

function opcion_6
{
OPCION_SUBDIR=""

echo ""
echo "6. Se mostrara la cantidad de archivos de cada tipo que contiene el directorio ingresado"
echo ""

echo -n "Ingrese el PATH del directorio deseado: "
read RUTA_DIR

if [ -d $RUTA_DIR ]
then

	until [[ $OPCION_SUBDIR == "S" || $OPCION_SUBDIR == "s" ||  $OPCION_SUBDIR == "N" ||  $OPCION_SUBDIR == "n"  ]]
	do
		echo "Por defecto solamente se contaran los archivos del directorio, sin incluir los subdirectorios"
		echo ""
		echo -n "Desea incluir los subdirectorios? (S/N): "
		read OPCION_SUBDIR
	done
	
	if [[ $OPCION_SUBDIR == "S" || $OPCION_SUBDIR == "s" ]]
	then
	
		echo "SE INCLUIRAN TODOS LOS SUBDIRECTORIOS."
		echo ""
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO ARCHIVO REGULAR ES: $(find $RUTA_DIR -ignore_readdir_race -mindepth 1 -type f | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO DIRECTORIO ES: $(find $RUTA_DIR -ignore_readdir_race -mindepth 1 -type d | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO ENLACE SIMBOLICO ES: $(find $RUTA_DIR -ignore_readdir_race -mindepth 1 -type l | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO DISPOSITIVOS DE CARACTER ES: $(find $RUTA_DIR -mindepth 1 -ignore_readdir_race -type c | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO DISPOSITIVOS DE BLOQUE ES: $(find $RUTA_DIR -ignore_readdir_race -mindepth 1 -type b | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO NAMED PIPES ES: $(find $RUTA_DIR -ignore_readdir_race -mindepth 1 -type p | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO SOCKET ES: $(find $RUTA_DIR -ignore_readdir_race -mindepth 1 -type s | wc -l)"
		echo ""
	
	else
	
		echo ""
		echo "SE INCLUIRAN SOLAMENTE LOS ARCHIVOS DEL DIRECTORIO."
		echo "NO SE TENDRAN EN CUENTA LOS SUBDIRECTORIOS."
		echo ""
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO ARCHIVO REGULAR ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type f | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO DIRECTORIO ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type d | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO ENLACE SIMBOLICO ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type l | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO DISPOSITIVOS DE CARACTER ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type c | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO DISPOSITIVOS DE BLOQUE ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type b | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO NAMED PIPES ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type p | wc -l)"
		echo "LA CANTIDAD DE ARCHIVOS DE TIPO SOCKET ES: $(find $RUTA_DIR -mindepth 1 -maxdepth 1 -type s | wc -l)"
		echo ""
	
	fi
else
	echo "EL DIRECTORIO NO EXISTE"
fi
}

function funcion_salir
{
echo ""
echo "Hasta luego $USUARIO"
echo "Script finalizado"
echo ""
}

echo ""
echo "Bienvenido/a $USUARIO"
echo ""
echo "MENU DE OPCIONES"
echo ""

select opcion in $opciones
do
	if [[ $opcion = "Fibonacci" ]]
	then
		opcion_1
	elif [[ $opcion = "Numero_Invertido" ]]
	then
		opcion_2
	elif [[ $opcion = "Palindromos" ]]
	then
		opcion_3
	elif [[ $opcion = "Lineas_archivo" ]]
	then
		opcion_4
	elif [[ $opcion = "Ordenar_Numeros" ]]
	then
		opcion_5
	elif [[ $opcion = "Cantidad_archivos_tipo" ]]
	then
		opcion_6
	elif [[ $opcion = "Salir" ]]
	then
		funcion_salir
		exit 0
	else
		echo "Opcion incorrecta"
	fi
done
