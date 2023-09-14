from decimal import Decimal
import logging
import os

from dotenv import load_dotenv

from utils import moneyfmt


logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


config = load_dotenv()


# Salario mínimo legal vigente
# Fuente: https://acmineria.com.co/sitio/wp-content/uploads/2023/05/Decreto-N0002613-de-2022.pdf
SMMLV = SMMLV_2023 = Decimal('1160000')

# Subsidio de transporte / Auxilio conectividad
# FUente: https://acmineria.com.co/sitio/wp-content/uploads/2023/05/Decreto-N0002613-de-2022.pdf
TRANSPORTATION_SUBSIDY = Decimal('140606')
TRANSPORTATION_SUBSIDY_MAX_SALARY = 2 * SMMLV

HEALTH_BENEFIT_PERCENTAGE = Decimal('0.04')
PENSION_BENEFIT_PERCENTAGE = Decimal('0.04')


class Gnomina:

    def __init__(self, salary_base: Decimal, payment_days: int = 30):
        self.salary_base = salary_base
        self.payment_days = payment_days

        # Sueldo
        self.wage = self.salary_base / 30 * self.payment_days

        self.calculate()

    @property
    def is_comprehensive_salary(self) -> bool:
        """Es un salario integral? (salario que incluye prestaciones sociales) - Art 132 CST

        10 SMMLV + 30% (?)
        """
        COMPREHENSIVE_SALARY_MIN = 13 * SMMLV
        logger.info(f'Salario mínimo integral vigente: {moneyfmt(COMPREHENSIVE_SALARY_MIN)}')
        if self.salary_base >= COMPREHENSIVE_SALARY_MIN:
            return True
        return False

    @staticmethod
    def get_overtime_payment() -> Decimal:
        """Horas Extras y Recargos (Recargo Nocturno)"""
        return Decimal('0')

    def get_transportation_subsidy(self) -> Decimal:
        """
        Calcula el pago del auxilio de transporte.
        Se paga sólo si uno gana menos de 2 SMMLV"""
        logger.info(f'Subsidio de transporte: {moneyfmt(TRANSPORTATION_SUBSIDY)}')
        logger.info(f'Subsidio de transporte aplica para las personas que ganan hasta {moneyfmt(TRANSPORTATION_SUBSIDY_MAX_SALARY)}')

        if self.salary_base <= TRANSPORTATION_SUBSIDY_MAX_SALARY:
            return TRANSPORTATION_SUBSIDY
        return Decimal('0')

    @staticmethod
    def get_contribution_base_income(wages_earned: Decimal, transportation_subsidy: Decimal):
        """IBC - ingreso base de cotización.

        Es el monto del salario del trabajador que se usa
        para determinar el valor de los aportes que se deben hacer
        al sistema de seguridad social."""
        return wages_earned - transportation_subsidy

    @staticmethod
    def get_health_benefit(contribution_base_income: Decimal) -> Decimal:
        """Salud obligatoria"""
        return contribution_base_income * HEALTH_BENEFIT_PERCENTAGE

    @staticmethod
    def get_pension_benefit(contribution_base_income: Decimal) -> Decimal:
        """Pansion"""
        return contribution_base_income * PENSION_BENEFIT_PERCENTAGE

    @staticmethod
    def get_pension_solidarity_fund_percentage(contribution_base_income: Decimal) -> Decimal:
        """Calcula el porcentaje para el cálculo del
        Fondo de solidaridad pensional (FSP).
        """
        if contribution_base_income < SMMLV * 4:
            return Decimal('0')
        if SMMLV * 4 <= contribution_base_income < SMMLV * 16:
            return Decimal('1')
        if SMMLV * 16 <= contribution_base_income < SMMLV * 17:
            return Decimal('1.20')
        if SMMLV * 17 <= contribution_base_income < SMMLV * 18:
            return Decimal('1.40')
        if SMMLV * 18 <= contribution_base_income < SMMLV * 19:
            return Decimal('1.60')
        if SMMLV * 19 <= contribution_base_income < SMMLV * 20:
            return Decimal('1.80')
        return Decimal('2')

    def get_pension_solidarity_fund_value(self, contribution_base_income: Decimal) -> Decimal:
        percentage = self.get_pension_solidarity_fund_percentage(contribution_base_income=contribution_base_income)
        logger.info(f'Porsentaje FSP {moneyfmt(percentage)}')
        return contribution_base_income * percentage

    def get_sick_pay_deductions(self) -> Decimal:
        """TODO:
        Incapacidades de origen común:
            primeros 2 días asume empleador
            a partir del 3er día: 66.66% (el resto paga la EPS)
        Por accidentes laborales:
            ARL cubre 100%
        """
        return Decimal('0')

    def calculate(self):
        transportation_subsidy = self.get_transportation_subsidy()
        overtime_payment = self.get_overtime_payment()

        # Total devengado
        wages_earned = self.wage + overtime_payment + transportation_subsidy

        contribution_base_income = self.get_contribution_base_income(
            wages_earned=wages_earned,
            transportation_subsidy=transportation_subsidy,
        )
        health_benefit = self.get_health_benefit(contribution_base_income=contribution_base_income)
        pension_benefit = self.get_pension_benefit(contribution_base_income=contribution_base_income)
        pension_solidarity_fund_value = self.get_pension_solidarity_fund_value(contribution_base_income=contribution_base_income)
        sick_pay_deductions = self.get_sick_pay_deductions()

        deductions = health_benefit + pension_benefit + pension_solidarity_fund_value + sick_pay_deductions

        wages_paid = wages_earned - deductions

        # Print the results
        result = f'''
        🔮\t🔮\t🔮
        🧙Gnómina del salario base mensual:\t {moneyfmt(self.salary_base)}
        
        Días a pagar:\t {self.payment_days} días
        Horas Extras y Recargos:\t {moneyfmt(overtime_payment)}
        Auxilio transporte (si aplica):\t {moneyfmt(transportation_subsidy)}
        Sueldo:\t {moneyfmt(self.wage)}
        = Total devengado:\t {moneyfmt(wages_earned)}
        
        Ingreso base de cotización:\t {moneyfmt(contribution_base_income)}
        Salud obligatoria:\t {moneyfmt(health_benefit)}
        Pensión obligatoria:\t {moneyfmt(pension_benefit)}
        Fondo de solidaridad:\t {moneyfmt(pension_solidarity_fund_value)}
        Incapacidades:\t {moneyfmt(sick_pay_deductions)}
        = Total deducido:\t {moneyfmt(deductions)}

        Neto a pagar:\t {moneyfmt(wages_paid)}
        '''
        print(result)


if __name__ == '__main__':
    input_message = ('¿Cuál es tu salario base mensual?'
                   '(es el acuerdo del contrato laboral;'
                   'escríbelo en pesos colombianos sin puntos o comas)\n')

    # Salario base mensual
    env_input_salary = os.getenv('SALARY')
    if env_input_salary is not None:
        logger.info('Valor de SALARY entontrado en .env')
        input_salary = Decimal(env_input_salary)
    else:
        input_salary = Decimal(input(input_message))

    Gnomina(salary_base=input_salary)
