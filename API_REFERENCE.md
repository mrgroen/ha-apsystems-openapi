# APsystems OpenAPI User Manual

> Copyright © 2016-2025 Altenergy Power System Inc. All Rights Reserved

## Version History

| Version | Date       | Description                                                                      |
|---------|------------|----------------------------------------------------------------------------------|
| V1.0    | 2022/09/16 | First Document                                                                   |
| V1.1    | 2023/03/24 | Edit the token URL; Change the expiration time of refresh token                  |
| V1.2    | 2023/10/07 | Change the JWT Token authentication method to signature authentication method    |
| V1.3    | 2023/10/31 | Add meter interface                                                              |
| V1.4    | 2023/11/17 |                                                                                  |
| V1.5    | 2023/11/17 | Add inverter-level data API                                                      |
| V1.6    | 2024/02/07 | Optimize the interface for end user                                              |
| V1.7    | 2025/04/17 | Add Storage-level Data API                                                       |
| V1.8    | 2025/07/18 | Adapt to the shared sub user system                                              |

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Authenticate and Authorize](#2-authenticate-and-authorize)
  - [2.1 Register an OpenAPI Account](#21-register-an-openapi-account)
  - [2.2 Authentication](#22-authentication)
    - [2.2.1 Headers](#221-headers-fixed-request-header-information)
    - [2.2.2 Calculate the Signature](#222-calculate-the-signature)
  - [2.3 Authorization](#23-authorization)
  - [2.4 Base URL](#24-base-url)
- [3. API](#3-api)
  - [3.1 System Details API](#31-system-details-api)
  - [3.2 System-level Data API](#32-system-level-data-api)
  - [3.3 ECU-level Data API](#33-ecu-level-data-api)
  - [3.4 Meter-level Data API](#34-meter-level-data-api)
  - [3.5 Inverter-level Data API](#35-inverter-level-data-api)
  - [3.6 Storage-level Data API](#36-storage-level-data-api)
- [4. Annex](#4-annex)

---

## 1. Overview

Welcome to APsystems' OpenAPI for developer portal. Anyone can register an API account on the platform after the application to access the system details and system data.

The OpenAPI is a REST API and delivers data in JSON format via HTTPS. It has six categories:

- System Details API
- System-level Data API
- ECU-level Data API
- Meter-level Data API
- Inverter-level Data API
- Storage-level Data API

---

## 2. Authenticate and Authorize

### 2.1 Register an OpenAPI Account

Send an application email to APsystems' support email address with the information below:

- Who you are?
- Why do you want to register an OpenAPI account?
- What to do with the data?

When your application is approved, you will get an email with your **App Id** and **App Secret**.

| Parameter  | Type   | Description                                                                                                                                                     |
|------------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| App Id     | string | A unique identity id for each OpenAPI account. It is a 32-bit string with numbers and letters. It cannot be changed once signed.                                |
| App Secret | string | The password to verify the valid OpenAPI account to generate the access token and refresh token. It is a 12-bit string with numbers and letters. Email APsystems to change it. |

> **Note:** Keep the access information safe and secret, do not disclose it to others.

### 2.2 Authentication

If you have your App Id and App Secret, you can access the OpenAPI. You need to calculate a signature for each request.

#### 2.2.1 Headers: Fixed request header information

You need to put the common parameters into the headers of each API request.

| Parameter             | Required | Type   | Description                                                            |
|-----------------------|----------|--------|------------------------------------------------------------------------|
| X-CA-AppId            | Y        | string | The identity id of the OpenAPI account (App Id).                       |
| X-CA-Timestamp        | Y        | string | The timestamp you request the API.                                     |
| X-CA-Nonce            | Y        | string | UUID, a 32-bit string, e.g. `"5e36eab8295911ee90751eff13c2920b"`      |
| X-CA-Signature-Method | Y        | string | Algorithm: `"HmacSHA256"` or `"HmacSHA1"`                             |
| X-CA-Signature        | Y        | string | The signature to verify your request.                                  |

#### 2.2.2 Calculate the Signature

**Step 1:** Get the parameters from the API request:

- `HTTPMethod` (GET, POST, DELETE)
- `Headers` (X-CA-AppId, X-CA-Timestamp, X-CA-Nonce, X-CA-Signature-Method)
- `RequestPath` (The last segment of the path)

**Step 2:** Combine the parameters into one string:

```
stringToSign = X-CA-Timestamp + "/" + X-CA-Nonce + "/" + X-CA-AppId + "/" + RequestPath + "/" + HTTPMethod + "/" + X-CA-Signature-Method
```

**Step 3:** Calculate the signature with the algorithm.

Two supported algorithms:

**HmacSHA256:**

```java
Mac hmacSha256 = Mac.getInstance("HmacSHA256");
byte[] appSecretBytes = appSecret.getBytes(Charset.forName("UTF-8"));
hmacSha256.init(new SecretKeySpec(appSecretBytes, 0, appSecretBytes.length, "HmacSHA256"));
byte[] md5Result = hmacSha256.doFinal(stringToSign.getBytes(Charset.forName("UTF-8")));
String signature = Base64.getEncoder().encodeToString(md5Result);
```

**HmacSHA1:**

```java
Mac hmacSha1 = Mac.getInstance("HmacSHA1");
byte[] appSecretBytes = appSecret.getBytes(Charset.forName("UTF-8"));
hmacSha1.init(new SecretKeySpec(appSecretBytes, 0, appSecretBytes.length, "HmacSHA1"));
byte[] md5Result = hmacSha1.doFinal(stringToSign.getBytes(Charset.forName("UTF-8")));
String signature = Base64.getEncoder().encodeToString(md5Result);
```

### 2.3 Authorization

You can access the default data as long as you get your AppId and App Secret. In addition, you can choose the category corresponding to your business.

> **Note:** According to the access count and data range, it will cause different payments.

### 2.4 Base URL

```
https://api.apsystemsema.com:9282
```

---

## 3. API

### 3.1 System Details API

#### 3.1.1 Get Details for a Particular System

- **URL:** `/user/api/v2/systems/details/{sid}`
- **Method:** `GET`
- **Description:** Returns the details of the system which you searched for.

**Parameters:**

| Parameter | Required | Type   | Description                          |
|-----------|----------|--------|--------------------------------------|
| sid       | Y        | string | The unique identity id of the system |

**Response:**

```json
{
  "data": {
    "sid": "AZ12649A3DFF",
    "create_date": "2022-09-01",
    "capacity": "1.28",
    "type": 1,
    "timezone": "Asia/Shanghai",
    "ecu": ["203000001234"],
    "light": 1,
    "authorization_code": "ff80808155 01b29d0155088b2ebb06ad"
  },
  "code": 0
}
```

**Response Fields:**

| Field                | Type   | Description                                                                                                                                                                                                                              |
|----------------------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| data.sid             | string | Unique identity id of the system.                                                                                                                                                                                                        |
| data.create_date     | string | Register date of the system in EMA. Format: `yyyy-MM-dd`                                                                                                                                                                                |
| data.capacity        | string | System size. Default unit is kW.                                                                                                                                                                                                         |
| data.type            | int    | System type. Default=1. `1` = PV system, `2` = Storage system, `3` = PV & storage system.                                                                                                                                               |
| data.timezone        | string | The timezone the ECU belongs to.                                                                                                                                                                                                         |
| data.ecu             | list   | ECU ids registered in this system. ECU such as `2030000001236-002405253708` is the shared sub user system: the "-" separates the main user ECU number from the sub user virtual ECU number. Subsequent queries should use the virtual ECU number. |
| data.light           | int    | System status light. `1` = Green (normal), `2` = Yellow (some inverters have alarms), `3` = Red (ECU network issue), `4` = Grey (no data uploaded yet).                                                                                 |
| data.authorization_code | string | Authorization code for embedded website access. Generated after selecting 'Allow visitors to access this system' in the EMA account settings.                                                                                         |
| code                 | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition).                                                                                                                                                                      |

---

#### 3.1.2 Get Inverters for a Particular System

- **URL:** `/user/api/v2/systems/inverters/{sid}`
- **Method:** `GET`
- **Description:** Returns all the devices of a system you searched for.

**Parameters:**

| Parameter | Required | Type   | Description                          |
|-----------|----------|--------|--------------------------------------|
| sid       | Y        | string | The unique identity id of the system |

**Response:**

```json
{
  "data": [
    {
      "eid": "203000001234",
      "type": 0,
      "timezone": "Asia/Shanghai",
      "inverter": [
        { "uid": "902000001234", "type": "QT2D" },
        { "uid": "902000001235", "type": "QT2D" }
      ]
    }
  ],
  "code": 0
}
```

**Response Fields:**

| Field               | Type   | Description                                                                                     |
|---------------------|--------|-------------------------------------------------------------------------------------------------|
| data                | list   | List of the devices sorted by ECU.                                                              |
| data[].eid          | string | Unique identity id of the ECU.                                                                  |
| data[].type         | int    | Type of the ECU. `0` = ECU, `1` = ECU with meter activated, `2` = ECU with storage activated.   |
| data[].timezone     | string | The timezone the ECU belongs to.                                                                |
| data[].inverter     | list   | List of the inverters connected to the ECU.                                                     |
| data[].inverter[].uid  | string | Unique identity id of the inverter.                                                          |
| data[].inverter[].type | string | Type of the inverter.                                                                        |
| data[].model        | string | Model of the storage-activated ECU.                                                             |
| data[].capacity     | string | The capacity of the storage-activated ECU. Default unit is kWh.                                 |
| code                | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition).                             |

---

#### 3.1.3 Get Meters for a Particular System

- **URL:** `/user/api/v2/systems/meters/{sid}`
- **Method:** `GET`
- **Description:** Returns all the meters of a system you searched for.

**Parameters:**

| Parameter | Required | Type   | Description                          |
|-----------|----------|--------|--------------------------------------|
| sid       | Y        | string | The unique identity id of the system |

**Response:**

```json
{
  "data": ["203000001234"],
  "code": 0
}
```

**Response Fields:**

| Field | Type | Description                                                         |
|-------|------|---------------------------------------------------------------------|
| data  | list | List of the meter IDs.                                              |
| code  | int  | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

### 3.2 System-level Data API

#### 3.2.1 Get Summary Energy for a Particular System

- **URL:** `/user/api/v2/systems/summary/{sid}`
- **Method:** `GET`
- **Description:** Returns the accumulative energy reported by inverters of a particular system.

**Parameters:**

| Parameter | Required | Type   | Description                          |
|-----------|----------|--------|--------------------------------------|
| sid       | Y        | string | The unique identity id of the system |

**Response:**

```json
{
  "data": {
    "today": "12.28",
    "month": "12.28",
    "year": "12.28",
    "lifetime": "12.28"
  },
  "code": 0
}
```

**Response Fields:**

| Field         | Type   | Description                                                         |
|---------------|--------|---------------------------------------------------------------------|
| data.today    | string | Accumulative energy reported by inverters today. Unit is kWh.       |
| data.month    | string | Accumulative energy reported by inverters this month. Unit is kWh.  |
| data.year     | string | Accumulative energy reported by inverters this year. Unit is kWh.   |
| data.lifetime | string | Accumulative energy reported by inverters in the system lifetime. Unit is kWh. |
| code          | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

#### 3.2.2 Get Energy in Period for a Particular System

- **URL:** `/user/api/v2/systems/energy/{sid}`
- **Method:** `GET`
- **Description:** Returns four levels of accumulative energy reported by inverters for a particular system.

Energy levels:
- **Hourly Energy:** Hourly energy in a day (length = 24, hours 0–23).
- **Daily Energy:** Daily energy in a natural month (length = days in month).
- **Monthly Energy:** Monthly energy in a natural year (length = 12).
- **Yearly Energy:** Yearly energy in a lifetime (length = years since installation).

**Parameters:**

| Parameter    | Required | Type   | Description                                                                                                                                                                                                                     |
|--------------|----------|--------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| sid          | Y        | string | The unique identity id of the system.                                                                                                                                                                                           |
| energy_level | Y        | string | The energy level. Available values: `"hourly"`, `"daily"`, `"monthly"`, `"yearly"`.                                                                                                                                             |
| date_range   | N        | string | The date range. Format depends on `energy_level`: `"hourly"` → `yyyy-MM-dd`, `"daily"` → `yyyy-MM`, `"monthly"` → `yyyy`, `"yearly"` → not required. If `date_range` is later than the current time, the request will be rejected. |

**Response:**

```json
{
  "data": ["567.23", "550.32", "320.12"],
  "code": 0
}
```

**Response Fields:**

| Field | Type | Description                                                                                                                       |
|-------|------|-----------------------------------------------------------------------------------------------------------------------------------|
| data  | list | Energy list. Unit is kWh. Length: 24 (hourly), days in month (daily), 12 (monthly), years since installation (yearly).            |
| code  | int  | Response code. See [Annex 1](#41-annex-1-response-code-definition).                                                               |

---

### 3.3 ECU-level Data API

#### 3.3.1 Get Summary Energy for a Particular ECU

- **URL:** `/user/api/v2/systems/{sid}/devices/ecu/summary/{eid}`
- **Method:** `GET`
- **Description:** Returns the accumulative energy reported by inverters below an ECU.

**Parameters:**

| Parameter | Required | Type   | Description                     |
|-----------|----------|--------|---------------------------------|
| sid       | Y        | string | The identity id of the system.  |
| eid       | Y        | string | The identity id of ECU.         |

**Response:**

```json
{
  "data": {
    "today": "12.28",
    "month": "12.28",
    "year": "12.28",
    "lifetime": "12.28"
  },
  "code": 0
}
```

**Response Fields:**

| Field         | Type   | Description                                                             |
|---------------|--------|-------------------------------------------------------------------------|
| data.today    | string | Accumulative energy reported by inverters today. Unit is kWh.           |
| data.month    | string | Accumulative energy reported by inverters this month. Unit is kWh.      |
| data.year     | string | Accumulative energy reported by inverters this year. Unit is kWh.       |
| data.lifetime | string | Accumulative energy reported by inverters in the system lifetime. Unit is kWh. |
| code          | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition).     |

---

#### 3.3.2 Get Energy in Period for a Particular ECU

- **URL:** `/user/api/v2/systems/{sid}/devices/ecu/energy/{eid}`
- **Method:** `GET`
- **Description:** Returns five levels of accumulative energy reported by inverters below a particular ECU.

Energy levels:
- **Power Telemetry (minutely):** Power telemetry in a day.
- **Hourly Energy:** Hourly energy in a day (length = 24).
- **Daily Energy:** Daily energy in a natural month (length = days in month).
- **Monthly Energy:** Monthly energy in a natural year (length = 12).
- **Yearly Energy:** Yearly energy in a lifetime (length = years since installation).

**Parameters:**

| Parameter    | Required | Type   | Description                                                                                                                                                                                                                                  |
|--------------|----------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| sid          | Y        | string | The unique identity id of the system.                                                                                                                                                                                                        |
| eid          | Y        | string | The identity id of ECU.                                                                                                                                                                                                                      |
| energy_level | Y        | string | The energy level. Available values: `"minutely"`, `"hourly"`, `"daily"`, `"monthly"`, `"yearly"`.                                                                                                                                            |
| date_range   | N        | string | The date range. Format depends on `energy_level`: `"minutely"` → `yyyy-MM-dd`, `"hourly"` → `yyyy-MM-dd`, `"daily"` → `yyyy-MM`, `"monthly"` → `yyyy`, `"yearly"` → not required. If later than current time, the request will be rejected. |

**Response (hourly/daily/monthly/yearly):**

```json
{
  "data": ["567.23", "550.32", "320.12"],
  "code": 0
}
```

Energy list. Unit is kWh. Length varies by level: 24 (hourly), days in month (daily), 12 (monthly), years since installation (yearly).

**Response (minutely):**

```json
{
  "data": {
    "time": ["10:00", "10:05"],
    "energy": ["0.12", "0.15"],
    "power": ["150", "180"],
    "today": "12.28"
  },
  "code": 0
}
```

| Field      | Type   | Description                                                         |
|------------|--------|---------------------------------------------------------------------|
| data.time  | list   | Time list, each point in format `HH:mm`.                           |
| data.energy| list   | Energy list, corresponding to time. Unit is kWh.                    |
| data.power | list   | Power list, corresponding to time. Unit is W.                       |
| data.today | string | Accumulative energy produced on the day. Unit is kWh.               |
| code       | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

### 3.4 Meter-level Data API

#### 3.4.1 Get Summary Energy for a Particular Meter

- **URL:** `/user/api/v2/systems/{sid}/devices/meter/summary/{eid}`
- **Method:** `GET`
- **Description:** Returns the accumulative energy reported by a Meter ECU.

**Parameters:**

| Parameter | Required | Type   | Description                       |
|-----------|----------|--------|-----------------------------------|
| sid       | Y        | string | The identity id of the system.    |
| eid       | Y        | string | The identity id of Meter ECU.     |

**Response:**

```json
{
  "code": 0,
  "data": {
    "today": {
      "consumed": "394.408090",
      "exported": "0.000000",
      "imported": "560.523540",
      "produced": "833.884550"
    },
    "month": {
      "consumed": "394.408090",
      "exported": "0.000000",
      "imported": "560.523540",
      "produced": "833.884550"
    },
    "year": {
      "consumed": "6394.408090",
      "exported": "0.000000",
      "imported": "4560.523540",
      "produced": "1833.884550"
    },
    "lifetime": {
      "consumed": "6394.458090",
      "exported": "0.000000",
      "imported": "4561.643540",
      "produced": "1833.894550"
    }
  }
}
```

**Response Fields:**

| Field         | Type   | Description                                                         |
|---------------|--------|---------------------------------------------------------------------|
| data.today    | map    | Today's energy (consumed, exported, imported, produced).            |
| data.month    | map    | Energy of the month.                                                |
| data.year     | map    | Energy of the year.                                                 |
| data.lifetime | map    | Lifetime energy.                                                    |
| code          | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

#### 3.4.2 Get Energy in Period for a Particular Meter

- **URL:** `/user/api/v2/systems/{sid}/devices/meter/period/{eid}`
- **Method:** `GET`
- **Description:** Returns five levels of accumulative energy reported by inverters below a particular Meter ECU.

Energy levels:
- **Power Telemetry (minutely):** Power telemetry in a day.
- **Hourly Energy:** Hourly energy in a day (length = 24).
- **Daily Energy:** Daily energy in a natural month (length = days in month).
- **Monthly Energy:** Monthly energy in a natural year (length = 12).
- **Yearly Energy:** Yearly energy in a lifetime (length = years since installation).

**Parameters:**

| Parameter    | Required | Type   | Description                                                                                                                                                                                                                                  |
|--------------|----------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| sid          | Y        | string | The unique identity id of the system.                                                                                                                                                                                                        |
| eid          | Y        | string | The identity id of Meter ECU.                                                                                                                                                                                                                |
| energy_level | Y        | string | The energy level. Available values: `"minutely"`, `"hourly"`, `"daily"`, `"monthly"`, `"yearly"`.                                                                                                                                            |
| date_range   | N        | string | The date range. Format depends on `energy_level`: `"minutely"` → `yyyy-MM-dd`, `"hourly"` → `yyyy-MM-dd`, `"daily"` → `yyyy-MM`, `"monthly"` → `yyyy`, `"yearly"` → not required. If later than current time, the request will be rejected. |

**Response (hourly/daily/monthly/yearly):**

```json
{
  "code": 0,
  "data": {
    "time": ["01", "02"],
    "produced": ["40.300", "50.016"],
    "consumed": ["40.300", "50.016"],
    "imported": ["40.300", "50.016"],
    "exported": ["40.300", "50.016"]
  }
}
```

**Response (minutely):**

```json
{
  "code": 0,
  "data": {
    "today": {
      "consumed": "5.996600",
      "exported": "0.071860",
      "imported": "3.712280",
      "produced": "2.356180"
    },
    "time": ["23:57"],
    "power": {
      "consumed": ["167.96"],
      "imported_exported": ["167.96"],
      "produced": ["0.00"]
    },
    "energy": {
      "consumed": ["0.015620"],
      "exported": ["0"],
      "imported": ["0.01562"],
      "produced": ["0.00000"]
    }
  }
}
```

**Response Fields:**

| Field      | Type   | Description                                                         |
|------------|--------|---------------------------------------------------------------------|
| data.time  | list   | Time list, each point in format `HH:mm`.                           |
| data.energy| map    | Energy values (consumed, exported, imported, produced). Unit: kWh.  |
| data.power | map    | Power values (consumed, imported_exported, produced). Unit: W.      |
| data.today | map    | Accumulative energy produced on the day. Unit: kWh.                 |
| code       | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

### 3.5 Inverter-level Data API

#### 3.5.1 Get Summary Energy for a Particular Inverter

- **URL:** `/user/api/v2/systems/{sid}/devices/inverter/summary/{uid}`
- **Method:** `GET`
- **Description:** Returns the energy of an inverter.

**Parameters:**

| Parameter | Required | Type   | Description                          |
|-----------|----------|--------|--------------------------------------|
| sid       | Y        | string | The unique identity id of the system |
| uid       | Y        | string | The identity id of inverter          |

**Response:**

```json
{
  "data": {
    "d1": "12.28", "m1": "12.28", "y1": "12.28", "t1": "12.28",
    "d2": "12.28", "m2": "12.28", "y2": "12.28", "t2": "12.28",
    "d3": "12.28", "m3": "12.28", "y3": "12.28", "t3": "12.28",
    "d4": "12.28", "m4": "12.28", "y4": "12.28", "t4": "12.28"
  },
  "code": 0
}
```

**Response Fields (per channel 1–4):**

| Field | Type   | Description                                                  |
|-------|--------|--------------------------------------------------------------|
| d{n}  | string | Accumulative energy reported by channel N today. Unit: kWh.  |
| m{n}  | string | Accumulative energy reported by channel N this month. Unit: kWh. |
| y{n}  | string | Accumulative energy reported by channel N this year. Unit: kWh. |
| t{n}  | string | Accumulative energy reported by channel N lifetime. Unit: kWh. |
| code  | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

#### 3.5.2 Get Energy in Period for a Particular Inverter

- **URL:** `/user/api/v2/systems/{sid}/devices/inverter/energy/{uid}`
- **Method:** `GET`
- **Description:** Returns five levels of accumulative energy below a particular inverter.

Energy levels:
- **Power Telemetry (minutely):** Power telemetry in a day.
- **Hourly Energy:** Hourly energy in a day (length = 24).
- **Daily Energy:** Daily energy in a natural month (length = days in month).
- **Monthly Energy:** Monthly energy in a natural year (length = 12).
- **Yearly Energy:** Yearly energy in a lifetime (length = years since installation).

**Parameters:**

| Parameter    | Required | Type   | Description                                                                                                                                                                                                                                  |
|--------------|----------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| sid          | Y        | string | The unique identity id of the system.                                                                                                                                                                                                        |
| uid          | Y        | string | The identity id of inverter.                                                                                                                                                                                                                 |
| energy_level | Y        | string | The energy level. Available values: `"minutely"`, `"hourly"`, `"daily"`, `"monthly"`, `"yearly"`.                                                                                                                                            |
| date_range   | N        | string | The date range. Format depends on `energy_level`: `"minutely"` → `yyyy-MM-dd`, `"hourly"` → `yyyy-MM-dd`, `"daily"` → `yyyy-MM`, `"monthly"` → `yyyy`, `"yearly"` → not required. If later than current time, the request will be rejected. |

**Response (hourly/daily/monthly/yearly):**

```json
{
  "data": {
    "e1": ["567.23", "550.32", "320.12"],
    "e2": ["567.23", "550.32", "320.12"]
  },
  "code": 0
}
```

Energy list per channel (`e1`–`e4`). Unit is kWh. Length varies by level.

**Response (minutely):**

| Field   | Type | Description                  |
|---------|------|------------------------------|
| t       | list | Time list, format `HH:mm`.  |
| dc_p1–4 | list | DC Power on channels 1–4.   |
| dc_i1–4 | list | DC current on channels 1–4. |
| dc_v1–4 | list | DC voltage on channels 1–4. |
| dc_e1–4 | list | DC energy on channels 1–4.  |
| ac_v1–3 | list | AC voltage on channels 1–3. |
| ac_t    | list | AC temperature.              |
| ac_p    | list | AC power.                    |
| ac_f    | list | AC frequency.                |
| code    | int  | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

#### 3.5.3 Get Energy in a Day for All Inverters Below a Particular ECU

- **URL:** `/user/api/v2/systems/{sid}/devices/inverter/batch/energy/{eid}`
- **Method:** `GET`
- **Description:** Returns energy or power data for all inverters below a particular ECU for a given day.

**Parameters:**

| Parameter    | Required | Type   | Description                                                            |
|--------------|----------|--------|------------------------------------------------------------------------|
| sid          | Y        | string | The unique identity id of the system.                                  |
| eid          | Y        | string | The identity id of ECU.                                                |
| energy_level | Y        | string | Available values: `"power"`, `"energy"`.                               |
| date_range   | Y        | string | The date to query. Format: `yyyy-MM-dd`.                               |

**Response (energy_level = "energy"):**

```json
{
  "data": {
    "energy": ["701000001234-1-1.24", "701000001234-2-0.98"]
  },
  "code": 0
}
```

Energy list. The string format is `uid-channel-energy` (e.g., `701000001234-1-1.24`).

**Response (energy_level = "power"):**

```json
{
  "data": {
    "time": ["10:00", "10:05"],
    "power": {
      "701000001234-1": [45, 56, 78, 98]
    }
  },
  "code": 0
}
```

| Field      | Type | Description                                                                                          |
|------------|------|------------------------------------------------------------------------------------------------------|
| data.time  | list | Time list, each point in format `HH:mm`.                                                            |
| data.power | map  | Power per inverter-channel. Key format: `uid-channel`. Value: list of power values matching time length. Unit: W. |
| code       | int  | Response code. See [Annex 1](#41-annex-1-response-code-definition).                                  |

---

### 3.6 Storage-level Data API

#### 3.6.1 Get Latest Power for a Particular Storage

- **URL:** `/installer/api/v2/systems/{sid}/devices/storage/latest/{eid}`
- **Method:** `GET`
- **Description:** Returns the latest status of a Storage ECU.

**Parameters:**

| Parameter | Required | Type   | Description                        |
|-----------|----------|--------|------------------------------------|
| sid       | Y        | string | The identity id of the system.     |
| eid       | Y        | string | The identity id of Storage ECU.    |

**Response:**

```json
{
  "data": {
    "mode": "4",
    "soc": "97",
    "time": "23:57",
    "discharge": "394.408",
    "charge": "0.000",
    "produced": "560.523",
    "consumed": "560.523",
    "exported": "560.523",
    "imported": "833.884"
  },
  "code": 0
}
```

**Response Fields:**

| Field          | Type   | Description                                                         |
|----------------|--------|---------------------------------------------------------------------|
| data.mode      | string | Storage operation mode.                                             |
| data.soc       | string | Battery State of Charge. Unit: %.                                   |
| data.time      | string | Time of last reading.                                               |
| data.discharge | string | Last Discharge Power.                                               |
| data.charge    | string | Last Charge Power.                                                  |
| data.produced  | string | Last Produced Power.                                                |
| data.consumed  | string | Last Consumed Power.                                                |
| data.exported  | string | Last Exported Power.                                                |
| data.imported  | string | Last Imported Power.                                                |
| code           | int    | Response code. See [Annex 1](#41-annex-1-response-code-definition). |

---

#### 3.6.2 Get Summary Energy for a Particular Storage

- **URL:** `/installer/api/v2/systems/{sid}/devices/storage/summary/{eid}`
- **Method:** `GET`
- **Description:** Returns the accumulative energy reported by a Storage ECU.

**Parameters:**

| Parameter | Required | Type   | Description                        |
|-----------|----------|--------|------------------------------------|
| sid       | Y        | string | The identity id of the system.     |
| eid       | Y        | string | The identity id of Storage ECU.    |

**Response:**

```json
{
  "data": {
    "today": {
      "discharge": "394.408",
      "charge": "0.000",
      "produced": "560.523",
      "consumed": "560.523",
      "exported": "560.523",
      "imported": "833.884"
    },
    "month": {
      "discharge": "394.408",
      "charge": "0.000",
      "produced": "560.523",
      "consumed": "560.523",
      "exported": "560.523",
      "imported": "833.884"
    },
    "year": {
      "discharge": "394.408",
      "charge": "0.000",
      "produced": "560.523",
      "consumed": "560.523",
      "exported": "560.523",
      "imported": "833.884"
    },
    "lifetime": {
      "discharge": "394.408",
      "charge": "0.000",
      "produced": "560.523",
      "consumed": "560.523",
      "exported": "560.523",
      "imported": "833.884"
    }
  },
  "code": 0
}
```

**Response Fields:**

| Field         | Type | Description                                                              |
|---------------|------|--------------------------------------------------------------------------|
| data.today    | map  | Today's energy (discharge, charge, produced, consumed, exported, imported). |
| data.month    | map  | Energy of the month.                                                     |
| data.year     | map  | Energy of the year.                                                      |
| data.lifetime | map  | Lifetime energy.                                                         |
| code          | int  | Response code. See [Annex 1](#41-annex-1-response-code-definition).      |

---

#### 3.6.3 Get Energy in Period for a Particular Storage

- **URL:** `/installer/api/v2/systems/{sid}/devices/storage/period/{eid}`
- **Method:** `GET`
- **Description:** Returns five levels of accumulative energy reported by inverters below a particular Storage ECU.

Energy levels:
- **Power Telemetry (minutely):** Power telemetry in a day.
- **Hourly Energy:** Hourly energy in a day (length = 24).
- **Daily Energy:** Daily energy in a natural month (length = days in month).
- **Monthly Energy:** Monthly energy in a natural year (length = 12).
- **Yearly Energy:** Yearly energy in a lifetime (length = years since installation).

**Parameters:**

| Parameter    | Required | Type   | Description                                                                                                                                                                                                                                  |
|--------------|----------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| sid          | Y        | string | The unique identity id of the system.                                                                                                                                                                                                        |
| eid          | Y        | string | The identity id of Storage ECU.                                                                                                                                                                                                              |
| energy_level | Y        | string | The energy level. Available values: `"minutely"`, `"hourly"`, `"daily"`, `"monthly"`, `"yearly"`.                                                                                                                                            |
| date_range   | N        | string | The date range. Format depends on `energy_level`: `"minutely"` → `yyyy-MM-dd`, `"hourly"` → `yyyy-MM-dd`, `"daily"` → `yyyy-MM`, `"monthly"` → `yyyy`, `"yearly"` → not required. If later than current time, the request will be rejected. |

**Response (hourly/daily/monthly/yearly):**

```json
{
  "code": 0,
  "data": {
    "time": ["01", "02"],
    "discharge": ["40.300", "50.016"],
    "charge": ["40.300", "50.016"],
    "produced": ["40.300", "50.016"],
    "consumed": ["40.300", "50.016"],
    "exported": ["40.300", "50.016"],
    "imported": ["40.300", "50.016"]
  }
}
```

**Response (minutely):**

```json
{
  "code": 0,
  "data": {
    "today": {
      "discharge": "394.408",
      "charge": "0.000",
      "produced": "560.523",
      "consumed": "560.523",
      "exported": "560.523",
      "imported": "833.884"
    },
    "time": ["23:57"],
    "power": {
      "discharge": ["167.961"],
      "charge": ["167.961"],
      "produced": ["167.961"],
      "consumed": ["167.961"],
      "exported": ["167.961"],
      "imported": ["0.000"]
    },
    "energy": {
      "discharge": ["167.961"],
      "charge": ["167.961"],
      "produced": ["167.961"],
      "consumed": ["167.961"],
      "exported": ["167.961"],
      "imported": ["0.000"]
    }
  }
}
```

**Response Fields:**

| Field      | Type | Description                                                                    |
|------------|------|--------------------------------------------------------------------------------|
| data.time  | list | Time list, each point in format `HH:mm`.                                      |
| data.energy| map  | Energy values (discharge, charge, produced, consumed, exported, imported). Unit: kWh. |
| data.power | map  | Power values (discharge, charge, produced, consumed, exported, imported). Unit: W.    |
| data.today | map  | Accumulative energy produced on the day. Unit: kWh.                            |
| code       | int  | Response code. See [Annex 1](#41-annex-1-response-code-definition).            |

---

## 4. Annex

### 4.1 Annex 1. Response Code Definition

| Code | Description                                            |
|------|--------------------------------------------------------|
| 0    | Succeed to request.                                    |
| 1000 | Data exception.                                        |
| 1001 | No data.                                               |
| 2000 | Application account exception.                         |
| 2001 | Invalid application account.                           |
| 2002 | The application account is not authorized.             |
| 2003 | Application account authorization expires.             |
| 2004 | The application account has no permission.             |
| 2005 | The access limit of the application account was exceeded. |
| 3000 | Access token exception.                                |
| 3001 | Missing Access token.                                  |
| 3002 | Unable to verify Access token.                         |
| 3003 | Access token timeout.                                  |
| 3004 | Refresh token timeout.                                 |
| 4000 | Request parameter exception.                           |
| 4001 | Invalid request parameter.                             |
| 5000 | Internal server exception.                             |
| 6000 | Communication exception.                               |
| 7000 | Server access restriction exception.                   |
| 7001 | Server access limit exceeded.                          |
| 7002 | Too many requests, please request later.               |
| 7003 | The system is busy, please request later.              |
