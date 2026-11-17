/**
 * @file nrf_sdh_soc.h
 * @brief Stand-in for the nRF5 SDK header that main.c includes.
 *
 * main.c uses nothing from it by name. The stand-in is here so that the MISRA
 * C:2012 check (.github/workflows/style.yml) resolves every include of main.c.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_SDH_SOC_H__
#define NRF_SDH_SOC_H__

#endif /* NRF_SDH_SOC_H__ */
