/** Host-test stand-in for the USB driver. Traces to: BLE-DD-TEST. */
#ifndef NRF_DRV_USBD_H__
#define NRF_DRV_USBD_H__

#include <stdbool.h>

#define NRF_DRV_USBD_EPIN1	1
#define NRF_DRV_USBD_EPIN2	2
#define NRF_DRV_USBD_EPOUT1	3

bool nrf_drv_usbd_is_enabled(void);
void fake_usbd_set_enabled(bool enabled);

#endif
