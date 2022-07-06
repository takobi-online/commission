#  Copyright 2022 Simone Rubino - TAKOBI
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.addons.sale_commission.tests.test_common import TestCommon
from odoo.exceptions import ValidationError
from odoo.tools import dateutil


class TestCommissionFromOrder (TestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.commission_order = cls.commission_model.create({
            'name': 'test 50% on confirmed orders',
            'fix_qty': 50.0,
            'invoice_state': 'confirmed_orders',
        })
        cls.agent_monthly_order = cls.res_partner_model.create({
            'name': 'Test Agent - Monthly - Order',
            'agent': True,
            'settlement': 'monthly',
            'lang': 'en_US',
            'commission': cls.commission_order.id,
        })

    def test_cancel_settlement(self):
        """
        Check that cancelling a settlement
        allows to cancel the invoices linked to the order.
        """
        # Create and confirm the order
        sale_order = self._create_sale_order(
            self.agent_monthly_order,
            self.commission_order,
        )
        sale_order.action_confirm()

        # Create the settlements
        next_month = fields.Datetime.from_string(fields.Datetime.now()) \
            + dateutil.relativedelta.relativedelta(months=1)
        wizard = self.make_settle_model.create({
            'date_to': next_month,
        })
        settlements_action = wizard.action_settle()
        settlement = self.settle_model.search(settlements_action.get('domain'))
        self.assertEqual(len(settlement), 1)

        # Create the invoices for the order
        payment = self.advance_inv_model.create({
            'advance_payment_method': 'all',
        })
        context = {
            "active_model": 'sale.order',
            "active_ids": sale_order.ids,
            "active_id": sale_order.id,
        }
        payment.with_context(context).create_invoices()
        invoice = sale_order.invoice_ids
        self.assertEqual(len(invoice), 1)

        # Confirm the invoice for the order
        invoice.action_invoice_open()

        # Try to cancel the invoice
        invoice.move_id.journal_id.update_posted = True
        with self.assertRaises(ValidationError) as ve:
            invoice.action_invoice_cancel()
        exc_message = ve.exception.args[0]
        self.assertIn('invoice with settled lines', exc_message)

        # Cancel the settlement
        settlement.action_cancel()

        # Cancel the invoice
        invoice.action_invoice_cancel()
        self.assertEqual(invoice.state, 'cancel')
